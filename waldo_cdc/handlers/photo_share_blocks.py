from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['PhotoShareBlocksHandler']


class PhotoShareBlocksHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        if event.is_insert:
            self.send_to_photo_share_blocker(event, client,
                    endpoint=settings.photo_share_block_created_endpoint)
        if event.is_delete:
            self.send_to_photo_share_blocker(event, client,
                    endpoint=settings.photo_share_block_deleted_endpoint)

    def send_to_photo_share_blocker(self, event, client, endpoint):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.photo_share_blocker_routing_key,
                endpoint=endpoint,
                parameters=payload)
