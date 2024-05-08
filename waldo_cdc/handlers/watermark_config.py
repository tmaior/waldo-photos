from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient
from waldo_common.db.session import session_scope

LOG = get_logger()

__all__ = ['WatermarkConfigHandler']


class WatermarkConfigHandler(BaseHandler):
    def handle_event(self, event):
        client = AMQPClient()
        if event.is_insert or event.is_update:
            wc_uuid = event.get_row_data_value('watermark_config_uuid')
            client.send(routing_key=settings.photo_prep_routing_key,
                    endpoint=settings.watermark_config_updated_endpoint,
                    parameters={'uuid': wc_uuid})
