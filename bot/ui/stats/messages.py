from utils import get_message


def _load_range_presets() -> dict[str, tuple[str, int | None]]:
    raw = get_message("stats.ranges")
    if not isinstance(raw, dict):
        return {
            "week": ("Last Week", 7),
            "month": ("Last Month", 30),
            "six_months": ("Last 6 Months", 180),
            "all": ("All Time", None),
        }

    presets: dict[str, tuple[str, int | None]] = {}
    for key, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        label = cfg.get("label", key)
        days = cfg.get("days")
        presets[key] = (label, days)
    return presets or {
        "week": ("Last Week", 7),
        "month": ("Last Month", 30),
        "six_months": ("Last 6 Months", 180),
        "all": ("All Time", None),
    }


RANGE_PRESETS = _load_range_presets()


def stats_embed_scope_title(scope_label: str) -> str:
    return get_message("embeds.stats.scope_title", scope_label=scope_label)


def stats_chart_title(scope_label: str, chart_type: str) -> str:
    return get_message("embeds.stats.chart_title", scope_label=scope_label, chart_type=chart_type)


def stats_date_range_description(date_range_text: str, details: str | None = None) -> str:
    base = get_message("embeds.stats.date_range_prefix", date_range_text=date_range_text)
    if details:
        return f"{base}\n{details}"
    return base


def stats_menu_description(current_range: str) -> str:
    lines = [
        get_message("embeds.stats.menu.current_range_line", current_range=current_range),
        "",
        get_message("embeds.stats.menu.instructions_header"),
    ]
    instructions = get_message("embeds.stats.menu.instructions")
    if isinstance(instructions, list):
        lines.extend(f"- {line}" for line in instructions)
    return "\n".join(lines)


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
