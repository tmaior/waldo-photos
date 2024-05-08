from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient
from waldo_common.db.session import session_scope

LOG = get_logger()

__all__ = ['AlbumsMembershipsHandler']


class AlbumsMembershipsHandler(BaseHandler):
    def handle_event(self, event):
        if not event.is_delete:
            parameters = event.get_legacy_payload()
            with session_scope() as session:
                album_uuid, album_type = self.get_album_info(session, album_id=parameters['album_id'])
                account_uuid = self.get_account_uuid(session, account_id=parameters['receiver_account_id'])

            client = AMQPClient()
            if album_type == 'shutterbug':
                client.send(routing_key=settings.notifications_routing_key,
                        endpoint=settings.album_membership_status_endpoint,
                        parameters={**parameters, 'receiver_account_id': account_uuid, 'album_id': album_uuid})

            soft_deleted_changed = event.field_was_updated('soft_deleted')

            if event.is_insert:
                receiver_account_id = event.get_row_data_value('receiver_account_id')
                album_id = event.get_row_data_value('album_id')

                client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                    endpoint=settings.album_membership_created_endpoint,
                    parameters={'receiver_account_id': receiver_account_id,
                     'album_id': album_id})
            elif event.is_update and soft_deleted_changed:
                uuid = event.get_row_data_value('uuid')
                soft_deleted = event.get_row_data_value('soft_deleted')

                client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                    endpoint=settings.album_membership_updated_endpoint,
                    parameters={'album_membership_uuid': uuid,
                     'soft_deleted': soft_deleted})

    def get_album_info(self, session, album_id):
        STATEMENT = "SELECT uuid, album_type FROM albums WHERE id = :album_id"
        result = session.execute(STATEMENT, dict(album_id=album_id)).fetchone()
        return result['uuid'], result['album_type']

    def get_account_uuid(self, session, account_id):
        STATEMENT = "SELECT uuid FROM accounts WHERE id = :account_id"
        return session.execute(STATEMENT, dict(account_id=account_id)).fetchone()['uuid']
