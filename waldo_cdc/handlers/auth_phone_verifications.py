from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['AuthPhoneVerificationsHandler']


class AuthPhoneVerificationsHandler(BaseHandler):
    def handle_event(self, event):
        if event.is_insert:
            client = AMQPClient()
            payload = event.get_legacy_payload()
            client.send(routing_key=settings.slack_routing_key,
                    endpoint=settings.auth_phone_verification_created_endpoint,
                    parameters={'payload': payload})
