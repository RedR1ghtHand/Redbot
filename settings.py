import os

from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
CREATE_CHANNEL_ID = os.getenv("CREATE_CHANNEL_ID")
DEFAULT_CHANNEL_NAMES = os.getenv("DEFAULT_CHANNEL_NAMES").split(",")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "redbot")