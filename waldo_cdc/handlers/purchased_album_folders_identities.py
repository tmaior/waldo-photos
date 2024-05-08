from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['PurchasedAlbumFoldersIdentitiesHandler']


class PurchasedAlbumFoldersIdentitiesHandler(BaseHandler):
    def handle_event(self, event):
        if event.is_insert:
            payload = event.get_legacy_payload()
            client = AMQPClient()
            client.send(routing_key=settings.hive_next_routing_key,
                    endpoint=settings.purchased_album_folder_identity_created_endpoint,
                    parameters={'payload': payload})
