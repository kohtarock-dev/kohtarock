"""robots.txt を尊重する汎用HTMLポーリングソース。

RSSを提供していないショップ/フリマサイトの一覧ページを、CSSセレクタで
軽く定期ポーリングするための実装です。あくまで「自分の巡回ペースを自動化する」
ためのツールであり、以下を利用者側の責任で守ってください。

  - 対象サイトの利用規約(ToS)を確認し、禁止されていないこと
  - robots.txt で当該パスの取得が許可されていること(本実装は起動時に自動チェックし、
    disallow の場合はスキップしてログに警告を出します)
  - poll_interval_sec を十分に長く(目安: 30分以上)設定し、過度な負荷をかけないこと
"""
from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.sources.base import BaseSource, FetchedItem

logger = logging.getLogger(__name__)

USER_AGENT = "InventoryScraperBot/1.0 (+personal use; low-frequency polling; contact: owner via app settings)"

_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def _is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(origin)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(urljoin(origin, "/robots.txt"))
        try:
            rp.read()
        except Exception as exc:  # robots.txt が無い/読めない場合は保守的に許可扱いにしない
            logger.warning("robots.txt の取得に失敗しました (%s): %s", origin, exc)
            rp = None
        _robots_cache[origin] = rp
    if rp is None:
        # robots.txt を確認できない場合は安全側に倒してブロックする
        return False
    return rp.can_fetch(USER_AGENT, url)


class HtmlPoliteSource(BaseSource):
    type_name = "html_polite"

    def fetch(self, keywords: list[str]) -> list[FetchedItem]:
        list_url = self.config.get("list_url")
        if not list_url:
            logger.warning("%s: list_url が設定されていません", self.name)
            return []

        if not _is_allowed(list_url):
            logger.warning(
                "%s: robots.txt により %s の取得が許可されていないためスキップします",
                self.name,
                list_url,
            )
            return []

        try:
            resp = httpx.get(list_url, timeout=15.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("%s: ページ取得失敗: %s", self.name, exc)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        item_selector = self.config.get("item_selector")
        if not item_selector:
            logger.warning("%s: item_selector が設定されていません", self.name)
            return []

        items: list[FetchedItem] = []
        for node in soup.select(item_selector):
            link_node = node.select_one(self.config.get("link_selector", "a"))
            title_node = node.select_one(self.config.get("title_selector", ""))
            price_node = node.select_one(self.config.get("price_selector", ""))
            image_node = node.select_one(self.config.get("image_selector", "img"))

            href = link_node.get("href") if link_node else None
            if not href:
                continue
            url = urljoin(list_url, href)
            title = title_node.get_text(strip=True) if title_node else (link_node.get_text(strip=True) if link_node else "")
            if not title:
                continue

            price = None
            if price_node:
                price = _parse_price(price_node.get_text(strip=True))

            image_url = None
            if image_node:
                image_url = image_node.get("src") or image_node.get("data-src")
                if image_url:
                    image_url = urljoin(list_url, image_url)

            items.append(
                FetchedItem(
                    external_id=url,
                    title=title,
                    url=url,
                    price=price,
                    image_url=image_url,
                    shop_name=self.name,
                )
            )
        return items


def _parse_price(text: str) -> float | None:
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None
