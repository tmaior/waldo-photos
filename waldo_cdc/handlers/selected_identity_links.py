from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['SelectedIdentityLinksHandler']


class SelectedIdentityLinksHandler(BaseHandler):
    def handle_event(self, event):
        legacy_payload = event.get_legacy_payload()
        client = AMQPClient()

        if not event.is_delete:
            self.send_to_face_matcher(legacy_payload, client)

        rfc_parameters = {'operation': event.operation_name, **legacy_payload}
        self.send_to_reference_face_coordinator(rfc_parameters, client)

        if event.is_delete and legacy_payload['is_master'] is True:
            self.send_to_hive_next(legacy_payload, client)

    def send_to_face_matcher(self, parameters, client):
        client.send(routing_key=settings.face_matcher_routing_key,
                endpoint=settings.selected_identity_link_updated_endpoint,
                parameters=parameters)

    def send_to_reference_face_coordinator(self, parameters, client):
        client.send(routing_key=settings.reference_face_coordinator_routing_key,
                endpoint=settings.selected_identity_link_updated_endpoint,
                parameters=parameters)

    def send_to_hive_next(self, parameters, client):
        client.send(routing_key=settings.hive_next_routing_key,
                endpoint=settings.selected_identity_link_deleted_endpoint,
                parameters=parameters)
