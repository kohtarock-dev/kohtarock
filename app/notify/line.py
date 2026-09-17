"""LINE Messaging API で新着アイテムをプッシュ通知する。

LINE Notifyは2025年3月末で新規発行・順次廃止されたため、
LINE公式アカウント(Messaging API)を使用する。

個人利用では、通知を受け取る自分のLINEユーザーIDを特定する作業が
地味に手間なので、あえて「友だち全員に配信」するbroadcast APIを使う。
この公式アカウントの友だちは基本的に自分だけなので、実質的に自分専用の
プッシュ通知として機能する。

無料プランはメッセージ配信が月200通までという制限があるため、新着を
1件ずつ別メッセージにはせず、複数件をまとめて1通のテキストにまとめて
送信することで、同じ枠で多くの新着をカバーできるようにしている。
"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"

# 1通のテキストメッセージにまとめる新着件数。LINEのテキストメッセージは
# 最大5000文字までなので、余裕を持って収まる件数にしている。
ITEMS_PER_MESSAGE = 10
# LINEのメッセージ配信は1回のAPI呼び出しあたり最大5メッセージまで。
MESSAGES_PER_REQUEST = 5


class NotifiableItem(Protocol):
    """通知メッセージの組み立てに必要な属性だけを定義するインターフェース。

    DBに保存されたItem、CIの軽量ポーリングスクリプトが作る一時オブジェクト、
    どちらもこの形さえ満たせばそのまま notify_new_items に渡せる。
    """

    title: str
    price: float | None
    shop_name: str | None
    source_name: str
    url: str
    matched_keyword: str | None


def _format_item(item: NotifiableItem) -> str:
    price_str = f"{int(item.price):,}円" if item.price is not None else "価格不明"
    lines = [
        "■ " + item.title[:60],
        f"{price_str} / {item.shop_name or item.source_name}",
        item.url,
    ]
    return "\n".join(lines)


def _build_batch_message(items: list[NotifiableItem]) -> str:
    header = f"【新着 {len(items)}件】"
    body = "\n\n".join(_format_item(item) for item in items)
    return f"{header}\n\n{body}"


def notify_new_items(items: list[NotifiableItem]) -> None:
    if not settings.line_enabled:
        logger.debug("LINE通知が未設定のためスキップします")
        return
    if not items:
        return

    headers = {
        "Authorization": f"Bearer {settings.line_channel_access_token}",
        "Content-Type": "application/json",
    }

    # 複数件をまとめて1通のテキストにし、月200通の無料枠を圧迫しないようにする
    batches = [items[i : i + ITEMS_PER_MESSAGE] for i in range(0, len(items), ITEMS_PER_MESSAGE)]
    messages = [{"type": "text", "text": _build_batch_message(batch)} for batch in batches]

    with httpx.Client(timeout=10.0) as client:
        for i in range(0, len(messages), MESSAGES_PER_REQUEST):
            payload = {"messages": messages[i : i + MESSAGES_PER_REQUEST]}
            try:
                resp = client.post(BROADCAST_URL, headers=headers, json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("LINE通知送信に失敗しました: %s", exc)
