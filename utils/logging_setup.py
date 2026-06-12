import logging
import os
import sys


def setup_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level_value = getattr(logging, log_level, logging.INFO)

    logging.basicConfig(
        level=log_level_value,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    if log_level_value > logging.DEBUG:
        for name in ("disnake.gateway", "disnake.http"):
            logging.getLogger(name).setLevel(logging.WARNING)

    logging.info("Logging initialized with level: %s", log_level)
