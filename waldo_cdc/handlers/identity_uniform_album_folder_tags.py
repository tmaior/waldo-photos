from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['IdentityUniformAlbumFolderTagsHandler']


class IdentityUniformAlbumFolderTagsHandler(BaseHandler):
    def handle_event(self, event):
        if event.is_insert or event.is_update:
            legacy_payload = event.get_legacy_payload()
            if (legacy_payload['jersey_number'] is not None and
                    legacy_payload['uniform_album_folder_tag_level_uuid'] is not None):
                reduced_payload = {
                    'uniform_album_folder_tag_level_uuid': legacy_payload['uniform_album_folder_tag_level_uuid'],
                    'uniform_album_folder_tag_level_team_uuid': legacy_payload['uniform_album_folder_tag_level_team_uuid'],
                    'identity_album_folder_tag_uuid': legacy_payload['identity_album_folder_tag_uuid']
                }
                client = AMQPClient()
                client.send(routing_key=settings.state_routing_key,
                        endpoint=settings.jersey_number_updated_endpoint,
                        parameters=reduced_payload)
