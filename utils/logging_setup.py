import logging
import os


def setup_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logging.getLogger("discord").setLevel(log_level)
    logging.getLogger("pymongo").setLevel(log_level)
    logging.getLogger("motor").setLevel(log_level)
    logging.getLogger("asyncio").setLevel(log_level)

    logging.info(f"Logging initialized with level: {log_level}")
