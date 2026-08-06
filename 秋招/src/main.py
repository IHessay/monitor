"""Daily monitoring entrypoint."""
from __future__ import annotations

import hashlib
import logging
import os
import random
import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from src.config import load_config
from src.filter import check_match, format_matched_tags
from src.sogou import SogouBlockedError, create_session, resolve_sogou_link, search_articles
from src.state import State
from src.time_parser import parse_sogou_time
from src.wecom import build_message, send_markdown

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Shanghai")


def _article_id(title: str, account: str, publish_time: str) -> str:
    """Stable article ID based on title + account + publish time."""
    key = f"{title}|{account}|{publish_time}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _parse_publish_date(publish_time: str) -> date | None:
    """Best-effort parse of Sogou publish time string into a date."""
    return parse_sogou_time(publish_time)


def _resolve_article_url(session: requests.Session, art: dict) -> str | None:
    """Resolve the Sogou redirect link for a matched article."""
    href = art.get("sogou_href")
    if not href:
        return None
    return resolve_sogou_link(
        session,
        href,
        art.get("sogou_search_text", ""),
        art.get("sogou_referer", ""),
    )


def _fetch_query_articles(
    session: requests.Session,
    queries: list[str],
    max_pages_per_query: int,
    max_articles_total: int,
) -> list[dict]:
    """Fetch articles from Sogou for each query, stopping at the total cap."""
    articles: list[dict] = []

    for idx, query in enumerate(queries):
        if idx > 0:
            # Be polite: wait between queries.
            time.sleep(random.uniform(2, 5))

        logger.info("Searching query: %s", query)
        for page in range(1, max_pages_per_query + 1):
            if len(articles) >= max_articles_total:
                logger.info("Reached max_articles_total=%d; stopping search", max_articles_total)
                return articles

            try:
                page_articles = search_articles(session, query, page=page)
            except SogouBlockedError:
                logger.error("Sogou blocked for query=%r page=%d; stopping this query", query, page)
                break
            except Exception as exc:
                logger.exception("Unexpected error searching query=%r page=%d: %s", query, page, exc)
                break

            if not page_articles:
                logger.info("No more results for query=%r at page=%d", query, page)
                break

            articles.extend(page_articles)
            if len(articles) >= max_articles_total:
                logger.info("Reached max_articles_total=%d; stopping search", max_articles_total)
                return articles[:max_articles_total]

            if page < max_pages_per_query:
                time.sleep(random.uniform(2, 4))

    return articles[:max_articles_total]


def main() -> int:
    config = load_config()
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    webhook_key = config.get("wecom", {}).get("webhook_key", "")

    search_config = config.get("search", {})
    queries = search_config.get("queries", [])
    max_pages_per_query = search_config.get("max_pages_per_query", 3)
    max_articles_total = search_config.get("max_articles_total", 100)
    send_empty = search_config.get("send_empty_notice", False)
    filter_config = config.get("filter", {})

    if not queries:
        logger.warning("No search queries configured. Please set search.queries in config/monitor.yaml")
        return 0

    state = State.load()
    state.set_search_queries(queries)

    session = create_session()
    matched_articles: list[dict] = []
    seen_this_run: set[str] = set()

    articles = _fetch_query_articles(
        session,
        queries,
        max_pages_per_query=max_pages_per_query,
        max_articles_total=max_articles_total,
    )

    for art in articles:
        title = art.get("title", "")
        account = art.get("account", "")
        publish_time = art.get("publish_time", "")
        art_id = _article_id(title, account, publish_time)

        if art_id in seen_this_run or state.is_seen(art_id):
            logger.debug("Duplicate or already seen: %s", title)
            continue
        seen_this_run.add(art_id)

        pub_date = _parse_publish_date(publish_time)
        if state.is_first_run() and pub_date is not None:
            # On the very first run, ignore older articles to avoid flooding.
            today = datetime.now(TZ).date()
            if pub_date < today:
                logger.info("Skipping older article on first run: %s", title)
                state.add(art_id, title, account, "")
                continue

        match = check_match(
            title=title,
            snippet=art.get("snippet", ""),
            filter_config=filter_config,
        )
        if not match:
            continue

        logger.info("Matched article: %s", title)
        matched_articles.append(
            {
                "title": title,
                "account": account,
                "publish_time": publish_time,
                "matched_tags": format_matched_tags(match),
                "article_id": art_id,
                "_art": art,
            }
        )

    # Resolve links only for matched, unseen articles to minimize Sogou requests.
    new_articles: list[dict] = []
    for art in matched_articles:
        try:
            url = _resolve_article_url(session, art["_art"])
        except SogouBlockedError:
            logger.error("Sogou blocked while resolving article link for: %s", art["title"])
            continue
        except Exception as exc:
            logger.warning("Failed to resolve article link for %s: %s", art["title"], exc)
            continue

        if not url:
            logger.warning("Could not resolve URL for: %s", art["title"])
            continue

        art["url"] = url
        del art["_art"]
        new_articles.append(art)
        # Small delay between link resolutions.
        time.sleep(random.uniform(0.5, 1.5))

    if new_articles:
        today_str = datetime.now(TZ).strftime("%Y-%m-%d")
        message = build_message(today_str, new_articles)

        if dry_run:
            logger.info("[DRY RUN] Would send message:\n%s", message)
        else:
            try:
                send_markdown(message, webhook_key=webhook_key)
            except Exception as exc:
                logger.exception("Failed to send WeChat Work message: %s", exc)
                return 1

        # Mark as seen only after successful send (or dry-run to avoid re-notifying)
        for art in new_articles:
            state.add(art["article_id"], art["title"], art["account"], art["url"])
    else:
        logger.info("No new matching articles today")
        if send_empty and not dry_run:
            today_str = datetime.now(TZ).strftime("%Y-%m-%d")
            send_markdown(f"## 📭 {today_str} 暂无新的 2027 法学岗位招聘推送", webhook_key=webhook_key)

    state.touch_run()
    if not dry_run:
        state.save()
        logger.info("State saved")

    return 0


if __name__ == "__main__":
    sys.exit(main())
