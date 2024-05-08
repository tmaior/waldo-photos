from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['AlbumAlbumFolderTagsHandler']


class AlbumAlbumFolderTagsHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()

        album_uuid = event.get_row_data_value('album_uuid')

        client.send(routing_key=settings.photo_router_routing_key,
                endpoint=settings.album_tags_updated_endpoint,
                parameters={'album_uuid': album_uuid})
