"""XMLサイトマップの更新日から「直近で更新された商品」を検出するソース。

商品一覧ページや個別ページ自体がボット対策(Cloudflare等)でブロックされていても、
検索エンジン向けのXMLサイトマップ(robots.txtで案内されている公式なファイル)は
別扱いでアクセスできることがある。この仕組みは、サイトマップの<lastmod>を
使って「最近更新されたURL」だけを抽出する。

商品ページを読めないため、通知には商品名や価格を含められない
(更新日とリンクのみ)。リンク先は一般的なブラウザでアクセスする分には
Cloudflareのボット対策に引っかからず普通に開ける。
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import httpx

from app.sources.base import BaseSource, FetchedItem

logger = logging.getLogger(__name__)

USER_AGENT = "InventoryScraperBot/1.0 (+personal use; polite sitemap reader)"

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_sitemap(xml_bytes: bytes, recent_days: int, shop_name: str) -> list[FetchedItem]:
    """サイトマップXMLから、直近 recent_days 日以内に更新された商品URLを抽出する。

    ネットワークアクセスを伴わない純粋な関数にすることで、ユニットテストしやすくしている。
    """
    cutoff = date.today() - timedelta(days=recent_days)

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("%s: サイトマップの解析に失敗しました: %s", shop_name, exc)
        return []

    items: list[FetchedItem] = []
    for url_el in root.findall("sm:url", _SITEMAP_NS):
        loc_el = url_el.find("sm:loc", _SITEMAP_NS)
        lastmod_el = url_el.find("sm:lastmod", _SITEMAP_NS)
        if loc_el is None or not loc_el.text:
            continue
        loc = loc_el.text.strip()

        # クエリパラメータの無いURL(カテゴリ/トップページ等)は個別商品ではないため除外
        if not urlparse(loc).query:
            continue

        mod_date = None
        if lastmod_el is not None and lastmod_el.text:
            try:
                mod_date = datetime.fromisoformat(lastmod_el.text.strip()).date()
            except ValueError:
                mod_date = None
        if mod_date is None or mod_date < cutoff:
            continue

        items.append(
            FetchedItem(
                external_id=loc,
                title=f"更新日 {mod_date.isoformat()}(タイトルはリンク先でご確認ください)",
                url=loc,
                price=None,
                image_url=None,
                shop_name=shop_name,
            )
        )
    return items


class SitemapDiffSource(BaseSource):
    type_name = "sitemap_diff"

    def fetch(self, keywords: list[str]) -> list[FetchedItem]:
        sitemap_url = self.config.get("sitemap_url")
        if not sitemap_url:
            logger.warning("%s: sitemap_url が設定されていません", self.name)
            return []

        recent_days = int(self.config.get("recent_days") or 3)

        try:
            resp = httpx.get(sitemap_url, timeout=30.0, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("%s: サイトマップ取得失敗: %s", self.name, exc)
            return []

        return parse_sitemap(resp.content, recent_days, self.name)
