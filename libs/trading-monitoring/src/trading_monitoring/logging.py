import logging
from logging.handlers import RotatingFileHandler


def configure_logging(path):
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5),
            logging.StreamHandler(),
        ],
    )
