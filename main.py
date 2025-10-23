from utils.logging_setup import setup_logging

setup_logging()

from bot import run_bot

if __name__ == "__main__":
    run_bot()