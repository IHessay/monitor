"""Sogou WeChat search fetcher."""
from __future__ import annotations

import html
import logging
import math
import random
import re
import time
import warnings
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.state import TZ

logger = logging.getLogger(__name__)

SOGOU_BASE = "https://weixin.sogou.com"
SOGOU_SEARCH = "https://weixin.sogou.com/weixin"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://weixin.sogou.com/",
    "Connection": "keep-alive",
}

PADS_RE = re.compile(r'href\.substr\(a\+(\d+)\+parseInt\("(\d+)"\)\+b,1\)')
TIMECONVERT_RE = re.compile(r"timeConvert\('(\d+)'\)")


class SogouBlockedError(Exception):
    """Raised when Sogou shows a CAPTCHA or anti-bot page."""


class SogouParseError(Exception):
    """Raised when the expected HTML structure is not found."""


def create_session() -> requests.Session:
    """Create a requests session with realistic headers and warm-up cookies."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    try:
        # Warm-up request to obtain SNUID and other cookies.
        resp = session.get(SOGOU_BASE, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to warm up Sogou session: %s", exc)
    return session


def _detect_blocking(text: str) -> bool:
    """Detect common anti-bot / verification markers."""
    markers = [
        "请输入验证码",
        "您的访问出错了",
        "antispider",
        "验证码",
        "验证",
        "当前访问疑似",
    ]
    lower = text.lower()
    return any(m.lower() in lower for m in markers)


def _extract_sogou_pads(text: str) -> tuple[str, str] | None:
    """Extract the two numeric parameters used by Sogou's link obfuscation JS."""
    m = PADS_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    return None


def resolve_sogou_link(
    session: requests.Session,
    href: str,
    search_text: str,
    search_referer: str,
) -> str | None:
    """Decode a Sogou /link?url=... article URL into the real mp.weixin.qq.com URL.

    Algorithm reverse-engineered from WechatSogou (https://github.com/chyroc/WechatSogou).
    """
    if not href or not href.startswith("/link?url="):
        return None

    url = SOGOU_BASE + href
    pads = _extract_sogou_pads(search_text)
    if not pads:
        logger.warning("Could not extract Sogou pads from search page; skipping link")
        return None

    b = math.floor(random.random() * 100) + 1
    a = url.find("url=")
    c = url.find("&k=")

    if a != -1 and c == -1:
        char_index = int(pads[0]) + int(pads[1]) + a + b
        if char_index < len(url):
            h = url[char_index]
            url = f"{url}&k={b}&h={h}"
        else:
            logger.warning("Computed Sogou char index out of bounds")
            return None

    headers = {"Referer": search_referer}
    logger.debug("Resolving Sogou link: %s", url)
    resp = session.get(url, headers=headers, timeout=20)

    if _detect_blocking(resp.text) or "antispider" in resp.url:
        raise SogouBlockedError("Sogou blocked while resolving article link")

    base_urls = re.findall(r"var url = '(.*?)';", resp.text)
    parts = re.findall(r"url \+= '(.*?)';", resp.text)

    if not base_urls:
        logger.warning("No base url found in Sogou redirect response")
        return None

    real_url = base_urls[0] + "".join(parts)
    real_url = real_url.replace("@", "")
    if real_url.startswith("http://"):
        real_url = "https://" + real_url[7:]
    return real_url


def _extract_account_name(li: BeautifulSoup) -> str:
    """Try several selectors to get the official account name."""
    s_p = li.find("div", class_="s-p")
    if s_p:
        account_tag = s_p.find("span", class_="all-time-y2")
        if account_tag:
            return account_tag.get_text(strip=True)

    # Legacy / fallback selectors
    selectors = [
        ("a", {"class_": "account"}),
        ("a", {"href": re.compile(r"/weixin\?type=1")}),
        ("span", {"class_": "all-time-y2"}),
    ]
    for tag_name, kwargs in selectors:
        tag = li.find(tag_name, **kwargs)
        if tag and tag.get_text(strip=True):
            return tag.get_text(strip=True)

    fg_line = li.find("p", class_="fg-line")
    if fg_line:
        for a in fg_line.find_all("a"):
            text = a.get_text(strip=True)
            if text:
                return text
    return ""


def _extract_publish_time(li: BeautifulSoup) -> str:
    """Extract publish time from Sogou result, converting Unix timestamps when possible."""
    s_p = li.find("div", class_="s-p")
    if s_p:
        time_tag = s_p.find("span", class_="s2")
        if time_tag:
            script = time_tag.find("script")
            if script:
                m = TIMECONVERT_RE.search(script.string or "")
                if m:
                    ts = int(m.group(1))
                    try:
                        return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M")
                    except (ValueError, OSError):
                        pass
            text = time_tag.get_text(strip=True)
            if text:
                return text

    # Legacy fallback
    time_tag = li.find("span", class_="all-time-y2") or li.find("span", class_="s2")
    return time_tag.get_text(strip=True) if time_tag else ""


def _parse_article_li(li: BeautifulSoup) -> dict[str, Any] | None:
    """Parse a single search result <li> into article metadata (without resolving links)."""
    title_tag = li.find("h3")
    if not title_tag:
        return None

    link = title_tag.find("a")
    if not link:
        return None

    title = link.get_text(strip=True)
    href = link.get("href", "")

    account = _extract_account_name(li)

    snippet_tag = li.find("p", class_="txt-info") or li.find("p", class_="news-info")
    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

    publish_time = _extract_publish_time(li)

    return {
        "title": title,
        "url": None,
        "sogou_href": href,
        "account": account,
        "publish_time": publish_time,
        "snippet": snippet,
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def search_articles(
    session: requests.Session,
    query: str,
    page: int = 1,
) -> list[dict[str, Any]]:
    """Search WeChat articles via Sogou and return parsed metadata.

    Raises SogouBlockedError if an anti-bot page is detected.
    """
    params = {
        "type": "2",
        "query": query,
        "page": page,
    }

    logger.info("Searching Sogou for query=%r page=%d", query, page)
    resp = session.get(SOGOU_SEARCH, params=params, timeout=20)
    resp.raise_for_status()

    text = resp.text
    if _detect_blocking(text):
        raise SogouBlockedError("Sogou returned an anti-bot / verification page")

    soup = BeautifulSoup(text, "lxml")
    news_list = soup.find("ul", class_="news-list")
    if not news_list:
        logger.warning("No news-list found for query=%r page=%d", query, page)
        return []

    referer = resp.url
    articles: list[dict[str, Any]] = []
    for li in news_list.find_all("li"):
        try:
            article = _parse_article_li(li)
        except Exception as exc:
            logger.warning("Failed to parse article li: %s", exc)
            continue
        if article:
            article["sogou_search_text"] = text
            article["sogou_referer"] = referer
            articles.append(article)

    logger.info("Found %d articles for query=%r page=%d", len(articles), query, page)
    return articles


def fetch_account_articles(
    session: requests.Session,
    account_name: str,
    max_articles: int = 10,
) -> list[dict[str, Any]]:
    """Fetch the latest articles for a specific official account name."""
    articles: list[dict[str, Any]] = []
    page = 1

    # Small warm-up delay before hammering Sogou.
    time.sleep(random.uniform(1, 3))

    while len(articles) < max_articles:
        try:
            page_articles = search_articles(session, account_name, page=page)
        except SogouBlockedError:
            logger.error("Sogou blocked while fetching account=%r", account_name)
            break
        except requests.RequestException as exc:
            logger.error("Network error fetching account=%r: %s", account_name, exc)
            break

        if not page_articles:
            break

        for art in page_articles:
            article_account = art.get("account") or ""
            # If we successfully parsed an account name, drop results from other accounts.
            if article_account and account_name not in article_account:
                logger.debug("Skipping article from different account: %r", article_account)
                continue
            articles.append(art)
            if len(articles) >= max_articles:
                break

        page += 1
        time.sleep(random.uniform(2, 4))

    return articles[:max_articles]


def discover_accounts(
    session: requests.Session,
    keywords: list[str],
    max_pages: int = 2,
) -> list[dict[str, Any]]:
    """Discover candidate official accounts by keyword search.

    .. deprecated::
        Account discovery is no longer part of the monitoring flow.
        Kept for manual/ad-hoc use only and may be removed in a future release.
    """
    warnings.warn(
        "discover_accounts is deprecated; monitoring now uses query-based article search",
        DeprecationWarning,
        stacklevel=2,
    )
    counter: dict[str, dict[str, Any]] = {}

    for keyword in keywords:
        for page in range(1, max_pages + 1):
            try:
                articles = search_articles(session, keyword, page=page)
            except SogouBlockedError:
                logger.error("Sogou blocked during discovery for keyword=%r", keyword)
                continue
            except requests.RequestException as exc:
                logger.error("Network error during discovery keyword=%r: %s", keyword, exc)
                continue

            for art in articles:
                account = art.get("account") or ""
                if not account:
                    continue
                if account not in counter:
                    counter[account] = {
                        "name": account,
                        "count": 0,
                        "sample_titles": [],
                        "source_queries": set(),
                    }
                counter[account]["count"] += 1
                counter[account]["source_queries"].add(keyword)
                if len(counter[account]["sample_titles"]) < 5:
                    counter[account]["sample_titles"].append(art.get("title", ""))

            time.sleep(random.uniform(1, 2))

    candidates = sorted(
        [
            {
                "name": v["name"],
                "article_count": v["count"],
                "sample_titles": v["sample_titles"],
                "source_queries": sorted(v["source_queries"]),
            }
            for v in counter.values()
        ],
        key=lambda x: x["article_count"],
        reverse=True,
    )
    return candidates
