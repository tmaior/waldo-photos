from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['AlbumFolderSharesHandler']


class AlbumFolderSharesHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        if event.is_insert:
            self.send_to_notifications(event, client,
                    endpoint=settings.album_folder_share_created_endpoint)
        elif event.is_update:
            self.send_to_hive_next(event, client,
                    endpoint=settings.album_folder_share_updated_endpoint)

    def send_to_hive_next(self, event, client, endpoint):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.hive_next_routing_key,
                endpoint=endpoint,
                parameters={'payload': payload})

    def send_to_notifications(self, event, client, endpoint):
        parameters = event.get_legacy_payload()
        client.send(routing_key=settings.notifications_routing_key,
                endpoint=endpoint,
                parameters=parameters)
