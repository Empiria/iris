from anvil_extras.logging import DEBUG, Logger
from routing import router

_LOG_LEVEL = DEBUG
_logger = Logger(name="Iris", level=_LOG_LEVEL)


class _Session:
    def __init__(self, logger):
        self.logger = logger
        self.launched = False

    def launch(self):
        if self.launched:
            return
        self.logger.debug("launching session...")
        self.terminate()
        router.launch()
        self.launched = True
        self.logger.debug("session launched")

    def terminate(self):
        router.clear_cache()
        self.logger.debug("session terminated")


session = _Session(logger=_logger)
