import pytest

from src.filter import check_match, format_matched_tags


@pytest.fixture
def filter_config():
    return {
        "law_keywords": ["法学", "法律", "律所", "法务"],
        "job_keywords": ["招聘", "实习", "校招", "秋招"],
        "year_patterns": ["2027", "2027届", "27届"],
        "negative": ["培训课", "考研", "广告"],
    }


def test_match_law_and_job(filter_config):
    assert check_match("某律所招聘实习生", "", filter_config) is not None


def test_match_year_and_job(filter_config):
    assert check_match("2027届校招启动", "", filter_config) is not None


def test_negative_excluded(filter_config):
    assert check_match("法学考研培训课程", "", filter_config) is None


def test_unrelated_excluded(filter_config):
    assert check_match("今日天气晴朗", "", filter_config) is None


def test_match_in_snippet(filter_config):
    assert check_match("某律所公告", "2027届校园招聘正式开始", filter_config) is not None


def test_format_matched_tags():
    match = {"year": ["2027届"], "law": ["法学"], "job": ["校招"]}
    text = format_matched_tags(match)
    assert "2027届" in text
    assert "法学" in text
    assert "校招" in text
