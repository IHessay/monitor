"""Candidate account discovery entrypoint."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from src.config import load_config, save_config
from src.sogou import create_session, discover_accounts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CANDIDATES_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.json"


def main() -> int:
    config = load_config()
    keywords = config.get("discover", {}).get("keywords", [])
    max_pages = config.get("discover", {}).get("max_pages", 2)

    if not keywords:
        logger.error("No discovery keywords configured in config/monitor.yaml")
        return 1

    logger.info("Starting discovery with %d keywords", len(keywords))
    session = create_session()
    candidates = discover_accounts(session, keywords, max_pages=max_pages)

    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATES_PATH.open("w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    logger.info("Discovered %d candidate accounts, saved to %s", len(candidates), CANDIDATES_PATH)
    for c in candidates[:20]:
        logger.info("  - %s (count=%d)", c["name"], c["article_count"])

    auto_top_n = config.get("discover", {}).get("auto_monitor_top_n", 0)
    auto_min_count = config.get("discover", {}).get("auto_monitor_min_count", 1)
    if auto_top_n:
        qualified = [c for c in candidates if c["article_count"] >= auto_min_count]
        selected = [c["name"] for c in qualified[:auto_top_n]]
        if selected:
            config["monitor"]["accounts"] = selected
            save_config(config)
            logger.info(
                "Auto-updated monitor.accounts with top %d accounts (min_count=%d)",
                len(selected),
                auto_min_count,
            )
        else:
            logger.warning("No candidates met auto_monitor criteria; monitor.accounts unchanged")

    return 0


if __name__ == "__main__":
    sys.exit(main())
