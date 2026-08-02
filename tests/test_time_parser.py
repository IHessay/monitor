from datetime import date, timedelta

import pytest

from src.time_parser import parse_sogou_time


def test_parse_yesterday():
    assert parse_sogou_time("昨天") == date.today() - timedelta(days=1)


def test_parse_relative_days():
    assert parse_sogou_time("3天前") == date.today() - timedelta(days=3)


def test_parse_absolute_date():
    assert parse_sogou_time("2024-08-01") == date(2024, 8, 1)


def test_parse_month_day():
    assert parse_sogou_time("08-01") == date(date.today().year, 8, 1)


def test_parse_time_only():
    assert parse_sogou_time("10:30") == date.today()


def test_parse_invalid():
    assert parse_sogou_time("") is None
    assert parse_sogou_time("unknown") is None
