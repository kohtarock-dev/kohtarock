"""GitHub Actions から定期実行する軽量ポーリングスクリプト。

FastAPIサーバーやDBを起動せず、config/sources.yaml のソースを1回ずつ巡回して
LINEに新着通知を送るだけの最小構成。既知アイテムの記録は data/seen.txt という
テキストファイル(1行1件、"ソース名|外部ID")に持たせ、ワークフロー側でこの
ファイルをリポジトリにコミットし直すことで、実行のたびに新しいGitHub Actions
ランナーが立ち上がっても「既に通知済みかどうか」を判定できるようにしている。
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_sources_config  # noqa: E402
from app.notify.line import notify_new_items  # noqa: E402
from app.sources.base import is_excluded, match_keywords  # noqa: E402
from app.sources.registry import build_source  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SEEN_FILE = Path(__file__).resolve().parent.parent / "data" / "seen.txt"
# 際限なく肥大化しないよう、直近何件までを保持するか
MAX_SEEN_LINES = 8000


@dataclass
class NotifiableItem:
    source_name: str
    title: str
    price: float | None
    url: str
    shop_name: str | None
    matched_keyword: str | None


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    return set(SEEN_FILE.read_text(encoding="utf-8").splitlines())


def save_seen(all_keys: list[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    trimmed = all_keys[-MAX_SEEN_LINES:]
    SEEN_FILE.write_text("\n".join(trimmed) + "\n", encoding="utf-8")


def main() -> None:
    config = load_sources_config()
    default_keywords = config.get("default_keywords", [])
    default_exclude = config.get("default_exclude_keywords", [])

    seen = load_seen()
    seen_order = list(seen)
    new_items: list[NotifiableItem] = []

    for src in config.get("sources", []):
        if not src.get("enabled"):
            continue
        name = src["name"]
        keywords = src.get("keywords") or default_keywords
        exclude_keywords = src.get("exclude_keywords") or default_exclude
        match_all = bool(src.get("match_all"))

        try:
            source = build_source(name, src["type"], src)
            fetched_items = source.fetch(keywords)
        except Exception:
            logger.exception("巡回中にエラーが発生しました: %s", name)
            continue

        for fetched in fetched_items:
            key = f"{name}|{fetched.external_id}"
            if key in seen:
                continue

            if match_all:
                if is_excluded(fetched.title, exclude_keywords):
                    continue
                matched_keyword = "(専門店・全件)"
            else:
                matched_keyword = match_keywords(fetched.title, keywords, exclude_keywords)
                if not matched_keyword:
                    continue

            seen.add(key)
            seen_order.append(key)
            new_items.append(
                NotifiableItem(
                    source_name=name,
                    title=fetched.title,
                    price=fetched.price,
                    url=fetched.url,
                    shop_name=fetched.shop_name or name,
                    matched_keyword=matched_keyword,
                )
            )

    if new_items:
        logger.info("新着 %d 件を検出しました。LINEに通知します。", len(new_items))
        notify_new_items(new_items)
    else:
        logger.info("新着はありませんでした。")

    save_seen(seen_order)


if __name__ == "__main__":
    main()
