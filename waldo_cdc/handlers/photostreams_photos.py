from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient
from waldo_common.db.session import session_scope

LOG = get_logger()

__all__ = ['PhotostreamsPhotosHandler']

PRE_DNP_STATUSES = ('published', 'reviewing')


class PhotostreamsPhotosHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        psp_uuid = str(event.get_row_data_value('uuid'))
        status = event.get_row_data_value('status')

        if event.is_update and event.field_was_updated('span_uuid'):
            # we don't want any CDC to happen if only span_uuid was updated
            return

        with session_scope() as session:
            if self.image_already_in_album(psp_uuid, session):
                if not event.is_delete:
                    self.delete_photostreams_photo(psp_uuid, session)
            elif ((not event.is_delete)
                  and status in PRE_DNP_STATUSES
                  and self.process_dnp(event, psp_uuid, session)):
                # if we are here, process_dnp has updated the psp, so we don't want to
                # perform all of the normal insert/update/delete handling
                if event.is_insert:
                    self.send_to_slack(event, client)
                    self.send_to_photo_router(event, client)
            else:
                if event.is_insert:
                    self.send_to_face_surveyor(event, client)
                    self.process_awaiting_matched_photos(event, psp_uuid, session)
                    self.send_to_slack(event, client)
                    self.send_to_photo_router(event, client)
                    self.send_to_matched_photo_aggregator(event, client,
                        settings.photostream_photo_created_endpoint)
                if event.is_update:
                    self.send_to_face_surveyor(event, client)
                    self.process_awaiting_matched_photos(event, psp_uuid, session)
                    if event.field_was_updated('status'):
                        self.send_to_matched_photo_aggregator(event, client,
                            settings.photostream_photo_updated_endpoint)
                if event.is_delete:
                    self.send_to_face_surveyor(event, client)
                    self.process_dnp_delete(event, session)
                    self.send_to_photo_router(event, client)
                    self.send_to_matched_photo_aggregator(event, client,
                        settings.photostream_photo_deleted_endpoint)


    def image_already_in_album(self, psp_uuid, session):
        STATEMENT = """
        SELECT other_psp.uuid
        FROM photostreams_photos this_psp
        JOIN photos this_p ON this_p.uuid = this_psp.photo_uuid
        JOIN photos other_p ON other_p.image_uuid = this_p.image_uuid
        JOIN photostreams_photos other_psp ON (other_psp.photo_uuid = other_p.uuid
                                               AND other_psp.photostream_id = this_psp.photostream_id)
        WHERE this_p.uuid <> other_p.uuid
          AND this_psp.uuid = :psp_uuid
        """
        other_psps_with_same_image_in_same_photostream = session.execute(STATEMENT, dict(psp_uuid=psp_uuid)).fetchall()
        return len(other_psps_with_same_image_in_same_photostream) > 0

    def delete_photostreams_photo(self, psp_uuid, session):
        STATEMENT = """
        DELETE FROM photostreams_photos
        WHERE uuid = :psp_uuid
        """
        session.execute(STATEMENT, dict(psp_uuid=psp_uuid))

    def process_dnp(self, event, psp_uuid, session):
        photo_uuid = event.get_row_data_value('photo_uuid')
        photostream_id = event.get_row_data_value('photostream_id')
        STATEMENT = """
        INSERT INTO dnp_face_statuses
            (compared_face_uuid, identity_uuid, selfie_face_uuid, status, photo_uuid)
            SELECT f.uuid, si.identities_uuid, rf.face_uuid, 'awaiting', p.uuid
                FROM selected_identities si
                JOIN albums_memberships am ON am.uuid = si.albums_memberships_uuid
                JOIN albums a on a.id = am.album_id
                JOIN photostreams ps on ps.id = a.photostream_id
                JOIN photostreams_photos psp on psp.photostream_id = ps.id
                JOIN photos p on p.id = psp.photo_id
                JOIN faces f on f.photo_id = p.uuid
                JOIN reference_faces rf on (rf.identity_uuid = si.identities_uuid
                                            and rf.album_uuid = a.uuid)
                WHERE p.uuid = :photo_uuid
                  AND ps.id = :photostream_id
                  AND si.is_invitee = false
                  AND si.is_dnp_blacklisted = true
                  AND f.faux_face_type IS NULL
                  AND rf.matching_halted_at IS NULL
        ON CONFLICT DO NOTHING
        RETURNING uuid
        """
        results = session.execute(STATEMENT, dict(photo_uuid=photo_uuid, photostream_id=photostream_id)).fetchall()
        num_inserted = len(results)

        # Update all dfs rows with existing face_match_votes if they correspond to this photo
        STATEMENT = """
        WITH fmvs AS (
            SELECT dfs.uuid as dfs_uuid,
                   CASE WHEN fmv.vote = 'positive' AND fmv.applied = true THEN dnp_face_status 'blocked'
                        WHEN fmv.vote = 'negative' THEN dnp_face_status 'cleared'
                        ELSE dnp_face_status 'awaiting'
                   END as new_dfs_status
            FROM face_match_votes fmv
            JOIN dnp_face_statuses dfs ON (fmv.identities_uuid = dfs.identity_uuid
                                       AND fmv.selfie_face_uuid = dfs.selfie_face_uuid
                                       AND fmv.compared_face_uuid = dfs.compared_face_uuid)
            WHERE fmv.compared_photo_uuid = :photo_uuid
            FOR UPDATE OF fmv
        )
        UPDATE dnp_face_statuses
        SET status = fmvs.new_dfs_status
        FROM fmvs
        WHERE fmvs.dfs_uuid = uuid
          AND dnp_face_statuses.status <> fmvs.new_dfs_status
        RETURNING uuid
        """
        results = session.execute(STATEMENT, dict(photo_uuid=photo_uuid)).fetchall()
        num_updated = len(results)

        some_were_inserted_or_updated = (num_inserted + num_updated) > 0

        if some_were_inserted_or_updated:
            UPDATE_STATEMENT = """
            UPDATE photostreams_photos
            SET status = 'awaiting-dnp-clearance'
            WHERE uuid = :psp_uuid
              AND status <> 'awaiting-dnp-clearance'
            """
            session.execute(UPDATE_STATEMENT, dict(psp_uuid=psp_uuid))

        return some_were_inserted_or_updated

    def process_awaiting_matched_photos(self, event, psp_uuid, session):
        status = event.get_row_data_value('status')
        if status in PRE_DNP_STATUSES:
            awaiting_matched_photo_infos = self.get_awaiting_matched_photo_infos(psp_uuid, session)
            for mp_info in awaiting_matched_photo_infos:
                LOG.debug("Clearing awaiting matched_photo",
                        psp_uuid=psp_uuid, mp_uuid=str(mp_info['uuid']))
                was_updated = self.clear_matched_photo(mp_info, session)
                if was_updated:
                    LOG.debug("Creating matched_photo_deliveries",
                            psp_uuid=psp_uuid, mp_uuid=str(mp_info['uuid']))
                    self.create_matched_photo_deliveries(mp_info, session)

    def get_awaiting_matched_photo_infos(self, psp_uuid, session):
        STATEMENT = """
        SELECT mp.*
        FROM photostreams_photos psp
        JOIN photostreams ps ON ps.id = psp.photostream_id
        JOIN matched_photos mp ON (mp.photos_uuid = psp.photo_uuid
                                   AND mp.photostreams_uuid = ps.uuid)
        WHERE psp.uuid = :psp_uuid
          AND mp.status = 'awaiting-dnp-clearance'
        """
        return session.execute(STATEMENT, dict(psp_uuid=psp_uuid)).fetchall()

    def clear_matched_photo(self, mp_info, session):
        STATEMENT = """
        UPDATE matched_photos
        SET status = 'cleared'
        WHERE status = 'awaiting-dnp-clearance'
          AND uuid = :mp_uuid
        RETURNING uuid
        """
        result = session.execute(STATEMENT, dict(mp_uuid=mp_info['uuid'])).fetchone()
        was_updated = result is not None
        return was_updated

    def create_matched_photo_deliveries(self, mp_info, session):
        STATEMENT = """
        SELECT si.*
        FROM selected_identities si
        JOIN albums_memberships am ON am.uuid = si.albums_memberships_uuid
        JOIN albums a ON a.id = am.album_id
        JOIN photostreams ps ON ps.id = a.photostream_id
        JOIN identities i ON i.uuid = si.identities_uuid
        JOIN matched_photos mp ON (mp.identities_uuid = i.uuid
                                   AND mp.photostreams_uuid = ps.uuid)
        JOIN accounts acc on acc.uuid = i.accounts_uuid
        WHERE mp.uuid = :mp_uuid
          AND am.soft_deleted = false
          AND acc.soft_deleted = false
        """
        si_infos = session.execute(STATEMENT, dict(mp_uuid=mp_info['uuid'])).fetchall()

        for si_info in si_infos:
            INSERT_STATEMENT = """
            INSERT INTO matched_photo_deliveries
                (matched_photo_uuid, selected_identity_uuid, status, is_invitee)
            VALUES
                (:mp_uuid, :si_uuid, 'cleared', :is_invitee)
            ON CONFLICT (matched_photo_uuid, selected_identity_uuid)
                DO NOTHING
            """
            session.execute(INSERT_STATEMENT, dict(mp_uuid=mp_info['uuid'], si_uuid=si_info['uuid'],
                is_invitee=si_info['is_invitee']))

            UPDATE_STATEMENT = """
            UPDATE matched_photo_deliveries
            SET status = 'cleared'
            WHERE matched_photo_uuid = :mp_uuid
              AND selected_identity_uuid = :si_uuid
              AND status = 'awaiting-dnp-clearance'
            """
            session.execute(UPDATE_STATEMENT, dict(mp_uuid=mp_info['uuid'], si_uuid=si_info['uuid']))

    def send_to_face_surveyor(self, event, client):
        operation = self.get_operation(event)
        parameters = event.get_legacy_payload()
        if operation == 'add':
            client.send(routing_key=settings.face_surveyor_routing_key,
                    endpoint=settings.photo_added_to_album_endpoint,
                    parameters=parameters,
                    priority=settings.general_priority)
        elif operation == 'remove':
            client.send(routing_key=settings.face_surveyor_routing_key,
                    endpoint=settings.photo_removed_from_album_endpoint,
                    parameters=parameters,
                    priority=settings.general_priority)

    def get_psp_info(self, event, session):
        ps_id = str(event.get_row_data_value('photostream_id'))
        STATEMENT = """
        SELECT ps.uuid as face_group_id,
               a.variant_uuid as variant_id
        FROM photostreams ps
        JOIN albums a on a.photostream_id = ps.id
        WHERE ps.id = :ps_id
        """
        return session.execute(STATEMENT, dict(ps_id=ps_id)).fetchone()

    def get_operation(self, event):
        if event.is_delete:
            return 'remove'
        else:
            status = event.get_row_data_value('status')
            if status in PRE_DNP_STATUSES:
                return 'add'
            elif status == 'awaiting-dnp-clearance':
                return 'add'
            elif status == 'machine-blocked':
                return 'add'
            elif event.is_update:
                return 'remove'
            else:
                return None

    def send_to_slack(self, event, client):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.slack_routing_key,
                endpoint=settings.photostreams_photos_created_endpoint,
                parameters={'payload': payload})

    def send_to_photo_router(self, event, client):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.photo_router_routing_key,
                endpoint=settings.photostreams_photo_inserted_endpoint,
                parameters={**payload, 'operation': event.operation_name})

    def send_to_matched_photo_aggregator(self, event, client, endpoint):
        uuid = event.get_row_data_value('uuid')
        photostream_id = event.get_row_data_value('photostream_id')
        photo_id = event.get_row_data_value('photo_id')
        client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                endpoint=endpoint,
                parameters={'photostream_photo_uuid': uuid,
                    'photostream_id': photostream_id, 'photo_id': photo_id})

    def process_dnp_delete(self, event, session):
        # Delete dfs rows if they are no longer dnp relevant.  They may still be relevant if
        # the photo is present in another album where that same identity+selfie_face is being
        # used for matching against it.
        STATEMENT = """
        WITH rfs AS (
            SELECT dfs.uuid as dfs_uuid,
                   rf.uuid as active_reference_face_uuid
            FROM dnp_face_statuses dfs
            LEFT JOIN photostreams_photos psp ON (psp.photo_uuid = dfs.photo_uuid
                                                   AND psp.photostream_id <> :ps_id)
            LEFT JOIN albums a ON (a.photostream_id = psp.photostream_id)
            LEFT JOIN reference_faces rf ON (rf.identity_uuid = dfs.identity_uuid
                                             AND rf.face_uuid = dfs.selfie_face_uuid
                                             AND rf.album_uuid = a.uuid
                                             AND rf.is_dnp_blacklisted = true
                                             AND rf.matching_halted_at IS NULL)
            WHERE dfs.photo_uuid = :p_uuid
        )
        DELETE FROM dnp_face_statuses
        USING rfs
        WHERE dnp_face_statuses.uuid = rfs.dfs_uuid
          AND rfs.active_reference_face_uuid IS NULL
        """
        ps_id = str(event.get_row_data_value('photostream_id'))
        p_uuid = str(event.get_row_data_value('photo_uuid'))
        session.execute(STATEMENT, dict(ps_id=ps_id, p_uuid=p_uuid))
