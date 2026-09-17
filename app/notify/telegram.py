"""Telegram Bot API で新着アイテムを通知する。

LINE公式アカウントの無料枠が月200通までと実用的でなかったため、
完全無料・通数制限の無いTelegramに切り替えた。

セットアップ:
  1. Telegramで @BotFather に /newbot を送りBotを作成、トークンを取得
  2. 作成したBotとのチャットを開始(何かメッセージを送る)
  3. https://api.telegram.org/bot<トークン>/getUpdates にアクセスし、
     自分の chat.id を確認する
"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"

# Telegramのテキストメッセージは最大4096文字。余裕を見て件数を決めている。
ITEMS_PER_MESSAGE = 20


class NotifiableItem(Protocol):
    """通知メッセージの組み立てに必要な属性だけを定義するインターフェース。"""

    title: str
    price: float | None
    shop_name: str | None
    source_name: str
    url: str
    matched_keyword: str | None


def _format_item(item: NotifiableItem) -> str:
    price_str = f"{int(item.price):,}円" if item.price is not None else "価格不明"
    lines = [
        f"■ {item.title[:60]}",
        f"{price_str} / {item.shop_name or item.source_name}",
        item.url,
    ]
    return "\n".join(lines)


def _build_batch_message(items: list[NotifiableItem]) -> str:
    header = f"【新着 {len(items)}件】"
    body = "\n\n".join(_format_item(item) for item in items)
    return f"{header}\n\n{body}"


def notify_new_items(items: list[NotifiableItem]) -> None:
    if not settings.telegram_enabled:
        logger.debug("Telegram通知が未設定のためスキップします")
        return
    if not items:
        return

    url = API_URL_TEMPLATE.format(token=settings.telegram_bot_token)
    batches = [items[i : i + ITEMS_PER_MESSAGE] for i in range(0, len(items), ITEMS_PER_MESSAGE)]

    with httpx.Client(timeout=10.0) as client:
        for batch in batches:
            payload = {
                "chat_id": settings.telegram_chat_id,
                "text": _build_batch_message(batch),
                "disable_web_page_preview": False,
            }
            try:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Telegram通知送信に失敗しました: %s", exc)
