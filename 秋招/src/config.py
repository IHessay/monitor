"""Configuration loader."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "monitor.yaml"


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load monitor configuration from YAML.

    Environment variable ``WECOM_WEBHOOK_KEY`` overrides the config file value.
    """
    if path is None:
        path = DEFAULT_CONFIG_PATH
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Backwards compatibility: old configs used monitor.accounts / discover.*.
    if config.get("monitor", {}).get("accounts"):
        logger.warning(
            "monitor.accounts is no longer used; configure search.queries instead"
        )
    if config.get("discover"):
        logger.warning("discover.* settings are deprecated and ignored")

    # Ensure all expected sections exist
    config.setdefault("search", {})
    config["search"].setdefault(
        "queries",
        [
            "2027校园招聘",
            "2027秋招",
            "2027校招",
            "2027届招聘",
        ],
    )
    config["search"].setdefault("max_pages_per_query", 3)
    config["search"].setdefault("max_articles_total", 100)
    config["search"].setdefault("send_empty_notice", False)

    config.setdefault("filter", {})
    config["filter"].setdefault("law_keywords", [])
    config["filter"].setdefault("job_keywords", [])
    config["filter"].setdefault("year_patterns", [])
    config["filter"].setdefault("negative", [])

    config.setdefault("wecom", {})
    config["wecom"].setdefault("webhook_key", "")

    # Allow secret override
    env_key = os.environ.get("WECOM_WEBHOOK_KEY")
    if env_key:
        config["wecom"]["webhook_key"] = env_key

    return config


def save_config(config: dict[str, Any], path: Path | str | None = None) -> None:
    """Save configuration back to YAML."""
    if path is None:
        path = DEFAULT_CONFIG_PATH
    path = Path(path)

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
