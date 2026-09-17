"""LINE Messaging API で新着アイテムをプッシュ通知する。

LINE Notifyは2025年3月末で新規発行・順次廃止されたため、
LINE公式アカウント(Messaging API)を使用する。

個人利用では、通知を受け取る自分のLINEユーザーIDを特定する作業が
地味に手間なので、あえて「友だち全員に配信」するbroadcast APIを使う。
この公式アカウントの友だちは基本的に自分だけなので、実質的に自分専用の
プッシュ通知として機能する。
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.db import Item

logger = logging.getLogger(__name__)

BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"


def _build_message(item: Item) -> str:
    price_str = f"{int(item.price):,}円" if item.price is not None else "価格不明"
    lines = [
        "【新着】" + item.title[:80],
        f"価格: {price_str}",
        f"出店: {item.shop_name or item.source_name}",
        item.url,
    ]
    if item.matched_keyword:
        lines.insert(1, f"キーワード: {item.matched_keyword}")
    return "\n".join(lines)


def notify_new_items(items: list[Item]) -> None:
    if not settings.line_enabled:
        logger.debug("LINE通知が未設定のためスキップします")
        return
    if not items:
        return

    headers = {
        "Authorization": f"Bearer {settings.line_channel_access_token}",
        "Content-Type": "application/json",
    }

    # LINEのメッセージは1回あたり最大5件まで。多い場合は分割して送信する。
    chunk_size = 5
    with httpx.Client(timeout=10.0) as client:
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            payload = {
                "messages": [{"type": "text", "text": _build_message(item)} for item in chunk],
            }
            try:
                resp = client.post(BROADCAST_URL, headers=headers, json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("LINE通知送信に失敗しました: %s", exc)
