from utils import get_message

RANGE_PRESETS: dict[str, tuple[str, int | None]] = {
    "week": ("Last Week", 7),
    "month": ("Last Month", 30),
    "six_months": ("Last 6 Months", 180),
    "all": ("All Time", None),
}


def stats_embed_scope_title(scope_label: str) -> str:
    return f"Voice Stats | {scope_label}"


def range_label(range_key: str) -> str:
    return RANGE_PRESETS.get(range_key, RANGE_PRESETS["week"])[0]


def range_days(range_key: str) -> int | None:
    return RANGE_PRESETS.get(range_key, RANGE_PRESETS["week"])[1]


def top_messages(limit: int):
    return {
        "title_template": get_message("embeds.top.title", limit=limit),
        "color_name": get_message("embeds.top.color"),
        "no_sessions": get_message("embeds.top.no_sessions"),
        "medals": get_message("embeds.top.medals"),
    }
