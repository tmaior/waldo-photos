from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['AccountsHandler']


class AccountsHandler(BaseHandler):
    def handle_event(self, event):
        soft_deleted_changed = event.field_was_updated('soft_deleted')
        if event.is_update and soft_deleted_changed:
            client = AMQPClient()

            soft_deleted = event.get_row_data_value('soft_deleted')
            account_uuid = event.get_row_data_value('uuid')
            client.send(routing_key=settings.matched_photo_aggregator_routing_key,
                    endpoint=settings.account_updated_endpoint,
                    parameters={'account_uuid': account_uuid, 'soft_deleted': soft_deleted})
