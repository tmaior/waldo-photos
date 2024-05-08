from structlog import get_logger

LOG = get_logger()

__all__ = ['BaseHandler', 'NullHandler', 'CrashingHandler']


class BaseHandler:
    def handle_event(self, event):
        raise NotImplementedError


class NullHandler(BaseHandler):
    def handle_event(self, event):
        LOG.debug("Handling CDC event", **event.to_dict_for_logging())


class CrashingHandler(BaseHandler):
    def handle_event(self, event):
        LOG.debug("Handling CDC event", **event.to_dict_for_logging())
        raise RuntimeError("Testing Error Handling")
