"""ソース(仕入れ先)共通のインターフェースとユーティリティ。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FetchedItem:
    """各ソースの実装が返す、正規化された商品情報。"""

    external_id: str
    title: str
    url: str
    price: float | None = None
    image_url: str | None = None
    shop_name: str | None = None
    condition: str | None = None


class BaseSource(ABC):
    """全ソース実装が継承する抽象クラス。"""

    type_name: str = "base"

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    def fetch(self, keywords: list[str]) -> list[FetchedItem]:
        """最新の商品一覧を取得する。

        keywords: API検索型のソース(楽天/Yahoo!ショッピング等)はこれを検索クエリとして使う。
                  RSS/HTMLポーリング型のソースは一覧をそのまま返してよい
                  (最終的なキーワード絞り込みは呼び出し側の match_keywords でも行われる)。
        """
        raise NotImplementedError


def is_excluded(title: str, exclude_keywords: list[str]) -> bool:
    """タイトルが exclude_keywords のいずれかを含むか判定する。"""
    if not title:
        return False
    lowered = title.lower()
    return any(ex and ex.lower() in lowered for ex in (exclude_keywords or []))


def match_keywords(title: str, keywords: list[str], exclude_keywords: list[str]) -> str | None:
    """タイトルが keywords のいずれかを含み、exclude_keywords をどれも含まない場合、
    最初にマッチしたキーワードを返す。マッチしなければ None。
    """
    if not title:
        return None
    if is_excluded(title, exclude_keywords):
        return None

    if not keywords:
        return None

    lowered = title.lower()
    for kw in keywords:
        if kw and kw.lower() in lowered:
            return kw
    return None
