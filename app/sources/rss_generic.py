"""汎用RSS/Atomフィード購読ソース。

ショップの新着RSSや、ヤフオク!の検索結果RSSなど、
サービス側が公式に配信しているフィードを購読する用途を想定しています。
"""
from __future__ import annotations

import logging
import re

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.sources.base import BaseSource, FetchedItem

logger = logging.getLogger(__name__)

USER_AGENT = "InventoryScraperBot/1.0 (+personal use; polite RSS reader)"

# 「価格: 12345」のように明示的にラベル付けされた金額だけを拾う。
# 「¥1,000」「1,000円」のような曖昧なパターンは、本文中の送料・割引条件等の
# 無関係な金額を誤って価格として拾ってしまう(実際に発生した)ため使用しない。
_PRICE_PATTERN = re.compile(r"価格[:：]\s*¥?([\d,]+)")


def _extract_price(html: str) -> float | None:
    if not html:
        return None
    # BeautifulSoupにHTMLタグを含まない短い文字列を渡すと
    # 「ファイル名に見える」という無害な警告が出るため、その場合は素通しする
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True) if "<" in html else html
    m = _PRICE_PATTERN.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


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
            html_body = ""
            if entry.get("content"):
                html_body = entry.content[0].get("value", "")
            elif entry.get("summary"):
                html_body = entry.summary

            image_url = None
            if "media_thumbnail" in entry and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get("url")
            elif entry.get("foaf_image"):
                # shop-pro.jp系のRSSが独自に埋め込む商品画像(foaf:Image)
                image_url = entry.foaf_image.get("rdf:about")
            elif "links" in entry:
                for link in entry.links:
                    if str(link.get("type", "")).startswith("image/"):
                        image_url = link.get("href")
                        break
            if not image_url and html_body:
                # ShopifyのAtomフィード等、本文HTML内に商品画像が埋め込まれているケースに対応
                img = BeautifulSoup(html_body, "lxml").find("img")
                if img and img.get("src"):
                    image_url = img["src"]

            price = _extract_price(html_body)

            items.append(
                FetchedItem(
                    external_id=external_id,
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    price=price,
                    image_url=image_url,
                    shop_name=self.name,
                )
            )
        return items
