from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['PubCommanderingIdentitiesHandler']


class PubCommanderingIdentitiesHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        if event.is_insert:
            self.send_to_slack(event, client,
                    endpoint=settings.pub_commandering_identity_created_endpoint)
        elif event.is_update:
            # only send to slack if if the 'needs_commandering' was just set to True
            if event.row_data_updates.get('needs_commandering', False):
                self.send_to_slack(event, client,
                        endpoint=settings.pub_commandering_identity_updated_endpoint)
        elif event.is_delete:
            self.send_to_slack(event, client,
                    endpoint=settings.pub_commandering_identity_deleted_endpoint)

    def send_to_slack(self, event, client, endpoint):
        payload = event.get_legacy_payload()
        client.send(routing_key=settings.slack_routing_key,
                endpoint=endpoint,
                parameters=payload)
