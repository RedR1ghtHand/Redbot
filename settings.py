import os

import yaml
from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CREATE_CHANNEL_IDS = [int(x.strip()) for x in os.getenv("CREATE_CHANNEL_IDS", "").split(",") if x.strip()]
DEFAULT_CHANNEL_NAMES = os.getenv("DEFAULT_CHANNEL_NAMES").split(",")

ALLOWED_GUILDS = {int(x.strip()) for x in os.getenv("ALLOWED_GUILDS", "").split(",") if x.strip()}

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "redbot")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MESSAGES_FILE = os.path.join(BASE_DIR, "messages.yaml")

with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
    MESSAGES = yaml.safe_load(f)
