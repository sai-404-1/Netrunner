import logging


class Logger:
    def __init__(self):
        logging.basicConfig(
            format = u'%(filename)s [LINE:%(lineno)d] | %(levelname)-4s | [%(asctime)s]  %(message)s',
            level = logging.INFO
        )
        self.logger = logging.getLogger("netrunner")
        self.logger.setLevel(logging.INFO)

    def debug(self, message, *args):
        self.logger.debug(message, *args)

    def info(self, message, *args):
        self.logger.info(message, *args)

    def warning(self, message, *args):
        self.logger.warning(message, *args)

    def error(self, message, *args):
        self.logger.error(message, *args)

    def critical(self, message, *args):
        self.logger.critical(message, *args)

    def exception(self, message, *args):
        self.logger.exception(message, *args)