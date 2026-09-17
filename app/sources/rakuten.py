"""楽天市場 商品検索API(公式)。

https://webservice.rakuten.co.jp/documentation/ichiba-item-search
利用には無料のアプリID登録が必要 (.env の RAKUTEN_APP_ID)。
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.sources.base import BaseSource, FetchedItem

logger = logging.getLogger(__name__)

API_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"

# 1ソース巡回あたりに問い合わせるキーワード数の上限(API呼び出し過多を避ける)
MAX_KEYWORDS_PER_POLL = 15


class RakutenApiSource(BaseSource):
    type_name = "rakuten_api"

    def fetch(self, keywords: list[str]) -> list[FetchedItem]:
        if not settings.rakuten_app_id:
            logger.warning("RAKUTEN_APP_ID が未設定のため %s をスキップします", self.name)
            return []

        results: dict[str, FetchedItem] = {}
        with httpx.Client(timeout=15.0) as client:
            for keyword in keywords[:MAX_KEYWORDS_PER_POLL]:
                params = {
                    "applicationId": settings.rakuten_app_id,
                    "keyword": keyword,
                    "sort": self.config.get("sort", "-updateTimestamp"),
                    "hits": 30,
                    "availability": 1,  # 在庫ありのみ
                }
                if self.config.get("genre_id"):
                    params["genreId"] = self.config["genre_id"]

                try:
                    resp = client.get(API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("楽天API取得失敗 (keyword=%s): %s", keyword, exc)
                    continue

                for entry in data.get("Items", []):
                    item = entry.get("Item", {})
                    code = item.get("itemCode")
                    if not code or code in results:
                        continue
                    images = item.get("mediumImageUrls") or []
                    image_url = None
                    if images:
                        image_url = images[0].get("imageUrl") if isinstance(images[0], dict) else images[0]
                    results[code] = FetchedItem(
                        external_id=code,
                        title=item.get("itemName", ""),
                        url=item.get("itemUrl", ""),
                        price=float(item["itemPrice"]) if item.get("itemPrice") is not None else None,
                        image_url=image_url,
                        shop_name=item.get("shopName"),
                    )
        return list(results.values())
