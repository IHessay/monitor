import tempfile
from pathlib import Path

import pytest

from src.config import load_config, save_config


def test_load_config_defaults():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write("filter:\n  law_keywords: [法学]\n")
        path = Path(f.name)

    try:
        config = load_config(path)
    finally:
        path.unlink()

    assert config["search"]["queries"] == [
        "2027校园招聘",
        "2027秋招",
        "2027校招",
        "2027届招聘",
    ]
    assert config["search"]["max_pages_per_query"] == 3
    assert config["search"]["max_articles_total"] == 100
    assert config["search"]["send_empty_notice"] is False
    assert config["filter"]["law_keywords"] == ["法学"]
    assert "discover" not in config


def test_load_config_reads_search_settings():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(
            "search:\n"
            "  queries:\n"
            "    - 2027校园招聘\n"
            "  max_pages_per_query: 1\n"
            "  max_articles_total: 5\n"
            "  send_empty_notice: true\n"
        )
        path = Path(f.name)

    try:
        config = load_config(path)
    finally:
        path.unlink()

    assert config["search"]["queries"] == ["2027校园招聘"]
    assert config["search"]["max_pages_per_query"] == 1
    assert config["search"]["max_articles_total"] == 5
    assert config["search"]["send_empty_notice"] is True


def test_save_and_load_roundtrip():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        path = Path(f.name)

    try:
        config = load_config(path)
        config["search"]["queries"] = ["测试查询"]
        save_config(config, path)
        reloaded = load_config(path)
    finally:
        path.unlink()

    assert reloaded["search"]["queries"] == ["测试查询"]


def test_webhook_key_override():
    import os

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write("wecom:\n  webhook_key: from-file\n")
        path = Path(f.name)

    os.environ["WECOM_WEBHOOK_KEY"] = "from-env"
    try:
        config = load_config(path)
    finally:
        path.unlink()
        os.environ.pop("WECOM_WEBHOOK_KEY", None)

    assert config["wecom"]["webhook_key"] == "from-env"
