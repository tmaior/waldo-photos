from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['MatchedPhotosHandler']


class MatchedPhotosHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        if event.is_insert:
            self.send_to_photo_share_blocker(event, client,
                    endpoint=settings.matched_photo_created_endpoint)
            self.send_to_matched_photo_aggregator(event, client)

        if event.is_delete:
            self.send_to_photo_share_blocker(event, client,
                    endpoint=settings.matched_photo_deleted_endpoint)

        if event.is_insert or event.is_delete:
            self.send_to_state(event, client,
                    endpoint=settings.matched_photo_updated_endpoint)

    def send_to_state(self, event, client, endpoint):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.state_routing_key,
                endpoint=endpoint,
                parameters=payload)

    def send_to_photo_share_blocker(self, event, client, endpoint):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.photo_share_blocker_routing_key,
                endpoint=endpoint,
                parameters=payload)

    def send_to_matched_photo_aggregator(self, event, client):
        uuid = event.get_row_data_value('uuid')
        client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                endpoint=settings.matched_photo_created_endpoint,
                parameters={'matched_photo_uuid': uuid})
