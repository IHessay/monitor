import hashlib
import os
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import main as main_module
from src.main import _article_id, _fetch_query_articles, main


@pytest.fixture
def state_path(tmp_path):
    return tmp_path / "state.json"


@pytest.fixture
def filter_config():
    return {
        "law_keywords": ["法学", "法律", "律所", "法务"],
        "job_keywords": ["招聘", "实习", "校招", "秋招"],
        "year_patterns": ["2027", "2027届", "27届"],
        "negative": ["培训课", "考研", "广告"],
    }


@pytest.fixture
def base_config(filter_config):
    return {
        "search": {
            "queries": ["2027校园招聘", "2027秋招"],
            "max_pages_per_query": 2,
            "max_articles_total": 10,
            "send_empty_notice": False,
        },
        "filter": filter_config,
        "wecom": {"webhook_key": "test-key"},
    }


def test_article_id_is_stable():
    assert _article_id("标题", "账号", "2025-01-01") == _article_id("标题", "账号", "2025-01-01")


def test_article_id_depends_on_all_fields():
    ids = {
        _article_id("标题", "账号", "2025-01-01"),
        _article_id("标题2", "账号", "2025-01-01"),
        _article_id("标题", "账号2", "2025-01-01"),
        _article_id("标题", "账号", "2025-01-02"),
    }
    assert len(ids) == 4


def test_fetch_query_articles_stops_at_total_cap():
    session = MagicMock()

    def fake_search(_session, query, page=1):
        return [
            {
                "title": f"{query}-p{page}-{i}",
                "account": "acc",
                "publish_time": "2025-01-01",
                "snippet": "",
            }
            for i in range(5)
        ]

    with patch.object(main_module, "search_articles", side_effect=fake_search):
        articles = _fetch_query_articles(
            session,
            queries=["q1", "q2"],
            max_pages_per_query=2,
            max_articles_total=7,
        )

    assert len(articles) == 7
    titles = [a["title"] for a in articles]
    assert titles[0].startswith("q1-p1-")
    assert titles[-1].startswith("q1-p2-")


def test_fetch_query_articles_returns_duplicates_across_queries():
    """Fetcher itself should not deduplicate; main() handles that."""
    session = MagicMock()

    shared = {
        "title": "重复文章",
        "account": "acc",
        "publish_time": "2025-01-01 10:00",
        "snippet": "",
    }

    def fake_search(_session, query, page=1):
        return [dict(shared)]

    with patch.object(main_module, "search_articles", side_effect=fake_search):
        articles = _fetch_query_articles(
            session,
            queries=["q1", "q2"],
            max_pages_per_query=1,
            max_articles_total=10,
        )

    assert len(articles) == 2


def test_main_sends_only_matching_articles(base_config, state_path):
    today = date.today().strftime("%Y-%m-%d %H:%M")

    def fake_search(_session, query, page=1):
        return [
            {
                "title": "某律所2027校招启动",
                "account": "法律招聘号",
                "publish_time": today,
                "snippet": "",
                "sogou_href": "/link?url=law",
                "sogou_search_text": "text",
                "sogou_referer": "ref",
            },
            {
                "title": "某互联网公司2027校园招聘",
                "account": "互联网招聘号",
                "publish_time": today,
                "snippet": "",
                "sogou_href": "/link?url=tech",
                "sogou_search_text": "text",
                "sogou_referer": "ref",
            },
        ]

    with (
        patch.object(main_module, "load_config", return_value=base_config),
        patch.object(main_module, "search_articles", side_effect=fake_search),
        patch.object(
            main_module,
            "resolve_sogou_link",
            return_value="https://mp.weixin.qq.com/s/article",
        ),
        patch.object(main_module, "send_markdown") as mock_send,
        patch("src.state.DEFAULT_STATE_PATH", state_path),
    ):
        result = main()

    assert result == 0
    assert mock_send.call_count == 1
    message = mock_send.call_args[0][0]
    assert "某律所2027校招启动" in message
    assert "互联网" not in message

    state = main_module.State.load(state_path)
    # Only the matching article is marked as seen.
    assert len(state.seen_article_ids) == 1


def test_main_respects_already_seen(base_config, state_path):
    today = date.today().strftime("%Y-%m-%d %H:%M")

    def fake_search(_session, query, page=1):
        return [
            {
                "title": "某律所2027校招启动",
                "account": "法律招聘号",
                "publish_time": today,
                "snippet": "",
                "sogou_href": "/link?url=law",
                "sogou_search_text": "text",
                "sogou_referer": "ref",
            }
        ]

    state = main_module.State()
    art_id = hashlib.sha256(f"某律所2027校招启动|法律招聘号|{today}".encode()).hexdigest()
    state.add(art_id, "某律所2027校招启动", "法律招聘号", "https://old.url")
    state.save(state_path)

    with (
        patch.object(main_module, "load_config", return_value=base_config),
        patch.object(main_module, "search_articles", side_effect=fake_search),
        patch.object(main_module, "send_markdown") as mock_send,
        patch("src.state.DEFAULT_STATE_PATH", state_path),
    ):
        result = main()

    assert result == 0
    mock_send.assert_not_called()


def test_main_dry_run_does_not_save_state(base_config, state_path):
    today = date.today().strftime("%Y-%m-%d %H:%M")

    def fake_search(_session, query, page=1):
        return [
            {
                "title": "某律所2027校招启动",
                "account": "法律招聘号",
                "publish_time": today,
                "snippet": "",
                "sogou_href": "/link?url=law",
                "sogou_search_text": "text",
                "sogou_referer": "ref",
            }
        ]

    with (
        patch.object(main_module, "load_config", return_value=base_config),
        patch.object(main_module, "search_articles", side_effect=fake_search),
        patch.object(
            main_module,
            "resolve_sogou_link",
            return_value="https://mp.weixin.qq.com/s/article",
        ),
        patch.object(main_module, "send_markdown") as mock_send,
        patch("src.state.DEFAULT_STATE_PATH", state_path),
    ):
        os.environ["DRY_RUN"] = "true"
        result = main()
        os.environ.pop("DRY_RUN", None)

    assert result == 0
    mock_send.assert_not_called()

    # State file should not be created/updated by a dry run.
    assert not Path(state_path).exists()


def test_main_skips_older_articles_on_first_run(base_config, state_path):
    def fake_search(_session, query, page=1):
        return [
            {
                "title": "旧文章",
                "account": "法律招聘号",
                "publish_time": "2020-01-01 10:00",
                "snippet": "某律所招聘",
                "sogou_href": "/link?url=old",
                "sogou_search_text": "text",
                "sogou_referer": "ref",
            }
        ]

    with (
        patch.object(main_module, "load_config", return_value=base_config),
        patch.object(main_module, "search_articles", side_effect=fake_search),
        patch.object(main_module, "send_markdown") as mock_send,
        patch("src.state.DEFAULT_STATE_PATH", state_path),
    ):
        result = main()

    assert result == 0
    mock_send.assert_not_called()

    state = main_module.State.load(state_path)
    assert len(state.seen_article_ids) == 1
