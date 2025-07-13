import logging
import os

datallog_log_level = os.getenv("DATALLOG_LOG_LEVEL", "INFO").upper()
if datallog_log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
    datallog_log_level = "INFO"
else:
    datallog_log_level = datallog_log_level

logging.basicConfig(
    level=datallog_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("../datallog.log", mode="a"),
    ],
)


class Logger:
    def __init__(self, file_name: str) -> None:
        self.__file_name = file_name

    def debug(self, message: str) -> None:
        logger = logging.getLogger(self.__file_name)
        logger.info(message)

    def info(self, message: str) -> None:
        logger = logging.getLogger(self.__file_name)
        logger.info(message)

    def warning(self, message: str) -> None:
        logger = logging.getLogger(self.__file_name)
        logger.warning(message)

    def error(self, message: str) -> None:
        logger = logging.getLogger(self.__file_name)
        logger.error(message)
