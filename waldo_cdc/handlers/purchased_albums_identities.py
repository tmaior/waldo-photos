from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['PurchasedAlbumsIdentitiesHandler']


class PurchasedAlbumsIdentitiesHandler(BaseHandler):
    def handle_event(self, event):
        if event.is_insert:
            payload = event.get_legacy_payload()
            client = AMQPClient()
            client.send(routing_key=settings.hive_next_routing_key,
                    endpoint=settings.purchased_album_identity_created_endpoint,
                    parameters={'payload': payload})

            purchased_album_uuid = event.get_row_data_value('purchased_albums_uuid')
            identity_uuid = event.get_row_data_value('identities_uuid')
            client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                endpoint=settings.purchased_album_identity_created_endpoint,
                parameters={'purchased_album_uuid': purchased_album_uuid, 'identity_uuid': identity_uuid})
