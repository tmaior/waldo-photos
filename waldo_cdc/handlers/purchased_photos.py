from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['PurchasedPhotosHandler']


class PurchasedPhotosHandler(BaseHandler):
    def handle_event(self, event):
        if event.is_insert:
            client = AMQPClient()

            account_id = event.get_row_data_value('account_id')
            photo_id = event.get_row_data_value('photo_id')
            client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                    endpoint=settings.purchased_photo_created_endpoint,
                    parameters={'account_id': account_id, 'photo_id': photo_id})
