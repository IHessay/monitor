"""Best-effort parser for Sogou WeChat search result time strings."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")


RELATIVE_PATTERN = re.compile(r"(\d+)\s*(天|小时|分钟)前")


def parse_sogou_time(time_str: str) -> date | None:
    """Convert a Sogou result time string into a date.

    Examples:
        - "3天前" -> today - 3 days
        - "昨天" -> today - 1 day
        - "前天" -> today - 2 days
        - "2024-08-01" -> 2024-08-01
        - "08-01" -> current year-08-01
        - "8月1日" -> current year-08-01
    """
    if not time_str:
        return None

    s = time_str.strip()
    today = datetime.now(TZ).date()

    # Relative days
    if s == "昨天":
        return today - timedelta(days=1)
    if s == "前天":
        return today - timedelta(days=2)

    m = RELATIVE_PATTERN.match(s)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if unit == "天":
            return today - timedelta(days=amount)
        # hours/minutes are still today
        return today

    # Absolute formats
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    # Month-day in current year (avoid deprecation warning for year-less parsing)
    md_patterns = [
        re.compile(r"^(\d{1,2})-(\d{1,2})$"),
        re.compile(r"^(\d{1,2})/(\d{1,2})$"),
        re.compile(r"^(\d{1,2})月(\d{1,2})日$"),
    ]
    for pat in md_patterns:
        m = pat.match(s)
        if m:
            try:
                return date(today.year, int(m.group(1)), int(m.group(2)))
            except ValueError:
                pass

    # Pure time like "10:30" -> today
    try:
        datetime.strptime(s, "%H:%M")
        return today
    except ValueError:
        pass

    return None
