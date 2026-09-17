"""ソースタイプ名 -> 実装クラス のレジストリ。"""
from __future__ import annotations

from app.sources.base import BaseSource
from app.sources.html_generic import HtmlPoliteSource
from app.sources.rakuten import RakutenApiSource
from app.sources.rss_generic import RssSource
from app.sources.yahoo_shopping import YahooShoppingApiSource

SOURCE_CLASSES: dict[str, type[BaseSource]] = {
    RakutenApiSource.type_name: RakutenApiSource,
    YahooShoppingApiSource.type_name: YahooShoppingApiSource,
    RssSource.type_name: RssSource,
    HtmlPoliteSource.type_name: HtmlPoliteSource,
}


def build_source(name: str, source_type: str, config: dict) -> BaseSource:
    cls = SOURCE_CLASSES.get(source_type)
    if cls is None:
        raise ValueError(f"未知のソースタイプです: {source_type}")
    return cls(name=name, config=config)
