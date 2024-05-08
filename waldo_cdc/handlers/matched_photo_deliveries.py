from .base import BaseHandler
from structlog import get_logger
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient

LOG = get_logger()

__all__ = ['MatchedPhotoDeliveriesHandler']


class MatchedPhotoDeliveriesHandler(BaseHandler):
    def handle_event(self, event):
        status = event.get_row_data_value('status')
        if status is None or status == 'cleared':
            mpd_uuid = event.get_row_data_value('uuid')
            client = AMQPClient()
            client.send(routing_key=settings.notifications_routing_key,
                    endpoint=settings.deliver_photo_endpoint,
                    parameters={'matched_photo_delivery_uuid': mpd_uuid})
