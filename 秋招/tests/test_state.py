import tempfile
from pathlib import Path

from src.state import State


def test_state_is_first_run_initially():
    state = State()
    assert state.is_first_run() is True


def test_state_seen_tracking():
    state = State()
    assert state.is_seen("abc") is False
    state.add("abc", "title", "account", "url")
    assert state.is_seen("abc") is True


def test_state_touch_run_sets_first_run_date():
    state = State()
    state.touch_run()
    assert state.is_first_run() is False
    assert state.first_run_date is not None
    assert state.last_run is not None


def test_state_save_and_load(tmp_path):
    path = tmp_path / "state.json"
    state = State()
    state.add("id1", "title", "account", "url")
    state.set_search_queries(["2027校园招聘"])
    state.touch_run()
    state.save(path)

    loaded = State.load(path)
    assert loaded.is_seen("id1")
    assert loaded.search_queries == ["2027校园招聘"]
    assert loaded.first_run_date == state.first_run_date


def test_state_migration_from_monitored_accounts(tmp_path):
    path = tmp_path / "state.json"
    legacy = {
        "version": 1,
        "last_run": "2025-01-01T10:00:00+08:00",
        "first_run_date": "2025-01-01",
        "seen_article_ids": {},
        "monitored_accounts": ["旧公众号"],
    }
    path.write_text(__import__("json").dumps(legacy), encoding="utf-8")

    loaded = State.load(path)
    assert loaded.search_queries == ["旧公众号"]
    assert not hasattr(loaded, "monitored_accounts")
