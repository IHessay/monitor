"""Persistent state management (seen articles)."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "state.json"
TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class ArticleRecord:
    title: str
    account: str
    url: str
    first_seen: str


@dataclass
class State:
    version: int = 1
    last_run: str | None = None
    first_run_date: str | None = None
    seen_article_ids: dict[str, dict[str, Any]] = field(default_factory=dict)
    search_queries: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "State":
        path = Path(path or DEFAULT_STATE_PATH)
        if not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Migrate legacy field name monitored_accounts -> search_queries.
        if "monitored_accounts" in data and "search_queries" not in data:
            data["search_queries"] = data.pop("monitored_accounts")
            logger.info("Migrated state: monitored_accounts -> search_queries")

        return cls(**data)

    def save(self, path: Path | str | None = None) -> None:
        path = Path(path or DEFAULT_STATE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    def is_seen(self, article_id: str) -> bool:
        return article_id in self.seen_article_ids

    def add(self, article_id: str, title: str, account: str, url: str) -> None:
        now = datetime.now(TZ).isoformat(timespec="seconds")
        self.seen_article_ids[article_id] = {
            "title": title,
            "account": account,
            "url": url,
            "first_seen": now,
        }

    def touch_run(self) -> None:
        now = datetime.now(TZ)
        self.last_run = now.isoformat(timespec="seconds")
        if self.first_run_date is None:
            self.first_run_date = now.date().isoformat()

    def is_first_run(self) -> bool:
        return self.first_run_date is None

    def is_before_first_run(self, article_date: date | None) -> bool:
        """Ignore articles published before the first run to avoid flooding history."""
        if self.first_run_date is None or article_date is None:
            return False
        return article_date < date.fromisoformat(self.first_run_date)

    def set_search_queries(self, queries: list[str]) -> None:
        self.search_queries = list(queries)
