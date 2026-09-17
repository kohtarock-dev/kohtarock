"""Yahoo!ショッピング 商品検索API(公式)。

https://developer.yahoo.co.jp/webapi/shopping/v3/itemsearch.html
利用には無料のアプリID登録が必要 (.env の YAHOO_APP_ID)。
"""
from __future__ import annotations

import logging
import time

import httpx

from app.config import settings
from app.sources.base import BaseSource, FetchedItem

logger = logging.getLogger(__name__)

API_URL = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"

MAX_KEYWORDS_PER_POLL = 15
REQUEST_INTERVAL_SEC = 1.1


class YahooShoppingApiSource(BaseSource):
    type_name = "yahoo_shopping_api"

    def fetch(self, keywords: list[str]) -> list[FetchedItem]:
        if not settings.yahoo_app_id:
            logger.warning("YAHOO_APP_ID が未設定のため %s をスキップします", self.name)
            return []

        results: dict[str, FetchedItem] = {}
        with httpx.Client(timeout=15.0) as client:
            for i, keyword in enumerate(keywords[:MAX_KEYWORDS_PER_POLL]):
                if i > 0:
                    time.sleep(REQUEST_INTERVAL_SEC)
                params = {
                    "appid": settings.yahoo_app_id,
                    "query": keyword,
                    "sort": "-update_time",
                    "results": 30,
                    "in_stock": "true",
                }
                try:
                    resp = client.get(API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("Yahoo!ショッピングAPI取得失敗 (keyword=%s): %s", keyword, exc)
                    continue

                for hit in data.get("hits", []):
                    code = hit.get("code")
                    if not code or code in results:
                        continue
                    image = hit.get("image") or {}
                    seller = hit.get("seller") or {}
                    price = hit.get("price")
                    results[code] = FetchedItem(
                        external_id=code,
                        title=hit.get("name", ""),
                        url=hit.get("url", ""),
                        price=float(price) if price is not None else None,
                        image_url=image.get("medium") or image.get("small"),
                        shop_name=seller.get("name"),
                        condition=hit.get("condition"),
                    )
        return list(results.values())
