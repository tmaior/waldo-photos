from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['FaceMatchVotesHandler']


class FaceMatchVotesHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        self.send_to_slack(event, client)
        if event.is_update and event.field_was_updated('cluster_uuid'):
            # we don't want any other CDC to happen if we're just updating cluster_uuid
            return

        self.send_to_time_matcher(event, client)
        self.send_to_reference_face_coordinator(event, client)
        self.send_to_face_matcher(event, client)

    def send_to_time_matcher(self, event, client):
        fmv_uuid = event.get_row_data_value('uuid')
        client.send(routing_key=settings.time_matcher_routing_key,
                endpoint=settings.face_match_vote_updated_endpoint,
                parameters={'uuid': fmv_uuid, 'operation': event.operation_name})

    def send_to_reference_face_coordinator(self, event, client):
        fmv_uuid = event.get_row_data_value('uuid')
        client.send(routing_key=settings.reference_face_coordinator_routing_key,
                endpoint=settings.face_match_vote_updated_endpoint,
                parameters={'uuid': fmv_uuid, 'operation': event.operation_name})

    def send_to_slack(self, event, client):
        legacy_payload = event.get_legacy_payload()

        if event.is_update and len(event.row_data_updates) == 2 and event.field_was_updated('cluster_uuid'):
            # only 'updated_at' and 'cluster_uuid' were updated
            only_cluster_uuid_was_updated = True
        else:
            only_cluster_uuid_was_updated = False
        legacy_payload['only_cluster_uuid_was_updated'] = only_cluster_uuid_was_updated

        client.send(routing_key=settings.slack_routing_key,
                endpoint=settings.face_match_vote_updated_endpoint,
                parameters={'payload': legacy_payload})

    def send_to_face_matcher(self, event, client):
        legacy_payload = event.get_legacy_payload()
        client.send(routing_key=settings.face_matcher_routing_key,
                endpoint=settings.face_match_vote_updated_endpoint,
                parameters=legacy_payload)
