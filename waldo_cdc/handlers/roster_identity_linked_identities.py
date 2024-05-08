from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['RosterIdentityLinkedIdentitiesHandler']


class RosterIdentityLinkedIdentitiesHandler(BaseHandler):
    def handle_event(self, event):
        endpoint = None
        if event.is_insert:
            endpoint = settings.roster_identity_linked_identity_created_endpoint
        if event.is_update:
            endpoint = settings.roster_identity_linked_identity_updated_endpoint

        if endpoint is not None:
            payload = event.get_legacy_payload()
            client = AMQPClient()
            client.send(routing_key=settings.photo_share_blocker_routing_key,
                    endpoint=endpoint,
                    parameters=payload)
