import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

load_dotenv()

_REPORTING_TZ_ENV = os.getenv("REPORTING_TIMEZONE", "UTC")


def get_reporting_timezone() -> ZoneInfo:
    """IANA zone used for activity-by-hour charts and labels (e.g. Europe/Kyiv). Invalid names fall back to UTC."""
    try:
        return ZoneInfo(_REPORTING_TZ_ENV)
    except Exception:
        return ZoneInfo("UTC")


REPORTING_TIMEZONE_NAME = _REPORTING_TZ_ENV


def _parse_env_utc_date(name: str, default: str | None = None) -> datetime | None:
    raw_value = os.getenv(name, default)
    if not raw_value:
        return None
    parsed = datetime.strptime(raw_value, "%Y-%m-%d")
    return parsed.replace(tzinfo=timezone.utc)


LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CREATE_CHANNEL_IDS = [int(x.strip()) for x in os.getenv("CREATE_CHANNEL_IDS", "").split(",") if x.strip()]
DEFAULT_CHANNEL_NAMES = os.getenv("DEFAULT_CHANNEL_NAMES").split(",")

ALLOWED_GUILDS = {int(x.strip()) for x in os.getenv("ALLOWED_GUILDS", "").split(",") if x.strip()}

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "redbot")

JOURNAL_METRICS_START_DATE = _parse_env_utc_date("JOURNAL_METRICS_START_DATE", "2026-05-01")

with open("messages_static.yaml", "r", encoding="utf-8") as f:
    MESSAGES_STATIC = yaml.safe_load(f)

if os.path.exists("messages.yaml"):
    with open("messages.yaml", "r", encoding="utf-8") as f:
        MESSAGES = yaml.safe_load(f)
else:
    MESSAGES = MESSAGES_STATIC
