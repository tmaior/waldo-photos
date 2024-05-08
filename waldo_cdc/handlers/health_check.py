from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['HealthCheckHandler']


class HealthCheckHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        client.raw_send(routing_key=settings.health_check_routing_key,
                payload={'status': "OK"})
