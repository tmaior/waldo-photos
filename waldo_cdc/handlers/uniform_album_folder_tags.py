from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient
from waldo_common.db.session import session_scope

LOG = get_logger()

__all__ = ['UniformAlbumFolderTagsHandler']


class UniformAlbumFolderTagsHandler(BaseHandler):
    def handle_event(self, event):
        if event.get_row_data_value('uniform_enabled') and event.get_row_data_value('uniform_numbered'):
            with session_scope() as session:
                STATEMENT = '''
                SELECT distinct album_uuid
                FROM album_album_folder_tags
                WHERE album_folder_tag_uuid = :album_folder_tag_uuid
                '''
                aft_uuid = event.get_row_data_value('album_folder_tag_uuid')
                results = session.execute(STATEMENT, dict(album_folder_tag_uuid=aft_uuid))

                client = AMQPClient()
                for row in results:
                    album_uuid = str(row['album_uuid'])
                    client.send(routing_key=settings.photo_router_routing_key,
                            endpoint=settings.album_tags_updated_endpoint,
                            parameters={'album_uuid': album_uuid})
