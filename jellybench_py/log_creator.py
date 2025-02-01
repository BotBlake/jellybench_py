import logging
import logging.handlers
import queue


class ColorizedFormatter(logging.Formatter):
    RESET_CODE = "\033[0m"
    COLOR_CODES = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red Background
    }

    def format(self, record):
        level_name = record.levelname
        color = self.COLOR_CODES.get(level_name, self.RESET_CODE)
        formatted_message = super().format(record)
        return f"{color}{formatted_message}{self.RESET_CODE}"


class LoggerConfig:
    def __init__(
        self,
        name: str,
        level: int,
        file: str = None,
        formatter: logging.Formatter = None,
    ):
        self.name = name
        self.level = level
        self.file = file
        self.formatter = formatter


class Logger:
    """
    Queue based logger to process messages asynchronously.
    """

    def __init__(self, config: LoggerConfig):
        self.config = config
        self._log_queue = queue.Queue()

        self._logger = logging.getLogger(self.config.name)
        self._logger.setLevel(self.config.level)

        queue_handler = logging.handlers.QueueHandler(self._log_queue)
        self._logger.addHandler(queue_handler)

        handlers = [logging.StreamHandler()]
        if self.config.file:
            handlers.append(logging.FileHandler(self.config.file))

        formatter = self.config.formatter or ColorizedFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        for handler in handlers:
            handler.setLevel(self.config.level)
            handler.setFormatter(formatter)

        self._listener = logging.handlers.QueueListener(self._log_queue, *handlers)

    def debug(self, msg: str):
        self._logger.debug(msg)

    def info(self, msg: str):
        self._logger.info(msg)

    def warning(self, msg: str):
        self._logger.warning(msg)

    def error(self, msg: str):
        self._logger.error(msg)

    def critical(self, msg: str):
        self._logger.critical(msg)

    def start(self):
        """Start queue listener."""
        self._listener.start()

    def stop(self):
        """Stop queue listener"""
        self._listener.stop()
