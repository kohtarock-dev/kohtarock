"""汎用RSS/Atomフィード購読ソース。

ショップの新着RSSや、ヤフオク!の検索結果RSSなど、
サービス側が公式に配信しているフィードを購読する用途を想定しています。
"""
from __future__ import annotations

import logging

import feedparser
import httpx

from app.sources.base import BaseSource, FetchedItem

logger = logging.getLogger(__name__)

USER_AGENT = "InventoryScraperBot/1.0 (+personal use; polite RSS reader)"


class RssSource(BaseSource):
    type_name = "rss"

    def fetch(self, keywords: list[str]) -> list[FetchedItem]:
        feed_url = self.config.get("feed_url")
        if not feed_url:
            logger.warning("%s: feed_url が設定されていません", self.name)
            return []

        try:
            resp = httpx.get(feed_url, timeout=15.0, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("%s: RSS取得失敗: %s", self.name, exc)
            return []

        parsed = feedparser.parse(resp.content)
        items: list[FetchedItem] = []
        for entry in parsed.entries:
            external_id = entry.get("id") or entry.get("link")
            if not external_id:
                continue
            image_url = None
            if "media_thumbnail" in entry and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get("url")
            elif "links" in entry:
                for link in entry.links:
                    if str(link.get("type", "")).startswith("image/"):
                        image_url = link.get("href")
                        break

            items.append(
                FetchedItem(
                    external_id=external_id,
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    image_url=image_url,
                    shop_name=self.name,
                )
            )
        return items
