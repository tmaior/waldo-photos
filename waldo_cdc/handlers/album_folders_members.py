from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['AlbumFoldersMembersHandler']


class AlbumFoldersMembersHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        if event.is_insert:
            self.send_to_hive_next(event, client,
                    endpoint=settings.album_folder_member_created_endpoint)

    def send_to_hive_next(self, event, client, endpoint):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.hive_next_routing_key,
                endpoint=endpoint,
                parameters={'payload': payload})
