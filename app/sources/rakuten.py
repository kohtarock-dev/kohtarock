"""楽天市場 商品検索API(公式)。

https://webservice.rakuten.co.jp/ (2026年2月にAPI基盤が移行され、
新エンドポイント openapi.rakuten.co.jp では applicationId に加えて
accessKey も必須になっている)。
利用には無料のアプリID登録が必要 (.env の RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY)。
"""
from __future__ import annotations

import logging
import time

import httpx

from app.config import settings
from app.sources.base import BaseSource, FetchedItem

logger = logging.getLogger(__name__)

API_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"

# 1ソース巡回あたりに問い合わせるキーワード数の上限(API呼び出し過多を避ける)
MAX_KEYWORDS_PER_POLL = 15

# アプリ登録時の「予想QPS」(1リクエスト/秒)を超えないよう、呼び出し間隔を空ける
REQUEST_INTERVAL_SEC = 1.1

# 新API基盤はアプリ登録時の「許可されたWebサイト」に一致するReferer/Originが無いと
# REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING で拒否される。
_REQUEST_HEADERS = {
    "Referer": "https://github.com/kohtarock-dev/kohtarock",
    "Origin": "https://github.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


class RakutenApiSource(BaseSource):
    type_name = "rakuten_api"

    def fetch(self, keywords: list[str]) -> list[FetchedItem]:
        if not settings.rakuten_app_id or not settings.rakuten_access_key:
            logger.warning(
                "RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY が未設定のため %s をスキップします", self.name
            )
            return []

        results: dict[str, FetchedItem] = {}
        with httpx.Client(timeout=15.0, headers=_REQUEST_HEADERS) as client:
            for i, keyword in enumerate(keywords[:MAX_KEYWORDS_PER_POLL]):
                if i > 0:
                    time.sleep(REQUEST_INTERVAL_SEC)
                params = {
                    "format": "json",
                    "applicationId": settings.rakuten_app_id,
                    "accessKey": settings.rakuten_access_key,
                    "keyword": keyword,
                    "genreId": self.config.get("genre_id") or 0,
                    "sort": self.config.get("sort", "-updateTimestamp"),
                    "hits": 30,
                    "availability": 1,  # 在庫ありのみ
                }

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
