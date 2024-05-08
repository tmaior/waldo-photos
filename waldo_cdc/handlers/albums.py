from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient
from waldo_common.db.session import session_scope

LOG = get_logger()

__all__ = ['AlbumsHandler']


class AlbumsHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        if event.is_insert:
            self.send_to_photo_prep(event, client)
            self.send_to_slack(event, client)
        elif event.is_update:
            self.maybe_soft_delete_albums_memberships(event)
            self.send_to_photo_prep(event, client)
            self.send_to_matched_photo_aggregator(event, client)
            self.maybe_send_to_photo_router(event, client)

    def maybe_send_to_photo_router(self, event, client):
        if event.row_data_updates.get('time_based_matching_enabled', False):
            client.send(routing_key=settings.photo_router_routing_key,
                    endpoint=settings.time_based_matching_enabled_endpoint,
                    parameters={'album_uuid': event.get_row_data_value('uuid')})

    def maybe_soft_delete_albums_memberships(self, event):
        if event.row_data_updates.get('soft_deleted', False):
            with session_scope() as session:
                STATEMENT = '''
                UPDATE albums_memberships
                SET soft_deleted = true
                WHERE album_id = :album_id
                  AND soft_deleted = false
                '''
                session.execute(STATEMENT, dict(album_id=event.get_row_data_value('id')))

    def send_to_photo_prep(self, event, client):
        if event.field_was_updated('watermark_config_id'):
            client.send(routing_key=settings.photo_prep_routing_key,
                    endpoint=settings.album_updated_endpoint,
                    parameters={'uuid': event.get_row_data_value('uuid')})

    def send_to_slack(self, event, client):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.slack_routing_key,
                endpoint=settings.album_created_endpoint,
                parameters={'payload': payload})

    def send_to_matched_photo_aggregator(self, event, client):
        uuid = event.get_row_data_value('uuid')
        soft_deleted_changed = event.field_was_updated('soft_deleted')
        soft_deleted = event.get_row_data_value('soft_deleted')
        if event.field_was_updated('album_type') or event.field_was_updated('album_subtype') or soft_deleted_changed:
            parameters={'album_uuid': uuid}
            if soft_deleted_changed:
                parameters['soft_deleted'] = soft_deleted

            client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                    endpoint=settings.album_updated_endpoint,
                    parameters=parameters)
