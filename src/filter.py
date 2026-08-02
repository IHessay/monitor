"""Article filtering by keywords."""
from __future__ import annotations

import re
from typing import Any


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, keywords: list[str]) -> list[str]:
    """Return the list of keywords found in text (case-insensitive)."""
    found = []
    for kw in keywords:
        if kw.lower() in text:
            found.append(kw)
    return found


def check_match(
    title: str,
    snippet: str,
    filter_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Return matched keywords if article passes filter, else None."""
    text = _normalize(title) + " " + _normalize(snippet)

    negative = filter_config.get("negative", [])
    if _contains_any(text, negative):
        return None

    law = _contains_any(text, filter_config.get("law_keywords", []))
    job = _contains_any(text, filter_config.get("job_keywords", []))
    year = _contains_any(text, filter_config.get("year_patterns", []))

    # Rule 1: law keyword + job keyword
    # Rule 2: year pattern (2027) + job keyword
    if (law and job) or (year and job):
        return {
            "law": law,
            "job": job,
            "year": year,
        }

    return None


def format_matched_tags(match: dict[str, list[str]]) -> str:
    """Format matched keywords for markdown display."""
    tags: list[str] = []
    if match.get("year"):
        tags.append("届别: " + ", ".join(match["year"]))
    if match.get("law"):
        tags.append("法学: " + ", ".join(match["law"]))
    if match.get("job"):
        tags.append("岗位: " + ", ".join(match["job"]))
    return "；".join(tags) if tags else "关键词匹配"
