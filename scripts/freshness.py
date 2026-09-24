"""Menu freshness: how old a place's menu or product list is against the kept age.

Principle "menu-freshness" (spine/stages/menus.json). The age and the warning
window are bindings (spine/bindings.json "menu-freshness", "time").
"""
from datetime import date, timedelta


def menu_age(as_of: str, today: str, max_age_days: int, warn_days: int) -> dict:
    """-> {"status": "current" | "due-soon" | "stale", "due": ISO date}."""
    due = date.fromisoformat(as_of) + timedelta(days=max_age_days)
    t = date.fromisoformat(today)
    if t > due:
        status = "stale"
    elif t >= due - timedelta(days=warn_days):
        status = "due-soon"
    else:
        status = "current"
    return {"status": status, "due": due.isoformat()}


def age_case(case: dict) -> dict:
    return menu_age(case["as_of"], case["today"], case["maxAgeDays"], case["warnDays"])
