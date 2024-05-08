from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['AlbumSharesHandler']


class AlbumSharesHandler(BaseHandler):
    def handle_event(self, event):
        parameters = event.get_legacy_payload()

        client = AMQPClient()
        client.send(routing_key=settings.notifications_routing_key,
                endpoint=settings.album_share_updated_endpoint,
                parameters=parameters)
