"""WeChat Work (企业微信) group bot sender."""
from __future__ import annotations

import json
import logging

import requests

WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"

logger = logging.getLogger(__name__)


def send_markdown(content: str, webhook_key: str, timeout: int = 30) -> bool:
    """Send a markdown message to a WeChat Work group bot.

    Raises RuntimeError on API failure.
    """
    if not webhook_key:
        raise RuntimeError("WECOM_WEBHOOK_KEY is not configured")

    url = WECOM_WEBHOOK_URL.format(key=webhook_key)
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }

    logger.info("Sending WeChat Work message (%d chars)", len(content))
    resp = requests.post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=timeout,
    )
    resp.raise_for_status()

    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"WeChat Work API error: {data}")

    logger.info("WeChat Work message sent successfully")
    return True


def build_message(date_str: str, articles: list[dict]) -> str:
    """Build a markdown message from matched articles."""
    lines = [f"## 🔔 2027 法学岗位招聘推送（{date_str}）\n"]
    for idx, article in enumerate(articles, 1):
        tags = article.get("matched_tags", "")
        lines.append(
            f"{idx}. **[{article['title']}]**（{article['account']}）\n"
            f"匹配：{tags}\n"
            f"[查看原文]({article['url']})\n"
        )
    lines.append("---\n如链接失效，可复制标题到微信搜一搜查找。")
    return "\n".join(lines)
