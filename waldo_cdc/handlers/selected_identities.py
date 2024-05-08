from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['SelectedIdentitiesHandler']


class SelectedIdentitiesHandler(BaseHandler):
    def handle_event(self, event):
        payload = event.get_legacy_payload()

        client = AMQPClient()
        if event.is_insert:
            self.send_to_slack(payload, client)
            self.send_to_hive_next(payload, client)

            if not event.get_row_data_value('is_invitee'):
                self.send_to_matched_photo_aggregator(event, client)

        if event.is_insert or event.is_delete:
            self.send_to_state(payload, event, client)

    def send_to_hive_next(self, payload, client):
        parameters = {'uuid': payload['uuid']}
        client.send(routing_key=settings.hive_next_routing_key,
                endpoint=settings.selected_identity_created_endpoint,
                parameters=parameters)

    def send_to_slack(self, payload, client):
        client.send(routing_key=settings.slack_routing_key,
                endpoint=settings.selected_identity_created_endpoint,
                parameters={'payload': payload})

    def send_to_state(self, payload, event, client):
        client.send(routing_key=settings.state_routing_key,
                endpoint=settings.selected_identity_updated_endpoint,
                parameters={'operation': event.operation_name, **payload})

    def send_to_matched_photo_aggregator(self, event, client):
        identity_uuid = event.get_row_data_value('identities_uuid')
        album_membership_uuid = event.get_row_data_value('albums_memberships_uuid')
        client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                endpoint=settings.selected_identity_created_endpoint,
                parameters={'identity_uuid': identity_uuid,
                    'album_membership_uuid': album_membership_uuid})
