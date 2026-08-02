"""Configuration loader."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


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

    # Ensure all expected sections exist
    config.setdefault("monitor", {})
    config["monitor"].setdefault("accounts", [])
    config["monitor"].setdefault("max_articles_per_account", 10)
    config["monitor"].setdefault("send_empty_notice", False)

    config.setdefault("discover", {})
    config["discover"].setdefault("keywords", [])
    config["discover"].setdefault("max_pages", 2)

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
