"""GitHub Actions から定期実行する軽量ポーリングスクリプト。

FastAPIサーバーやDBを起動せず、config/sources.yaml のソースを1回ずつ巡回して
LINEに新着通知を送るだけの最小構成。既知アイテムの記録は data/seen.txt という
テキストファイル(1行1件、"ソース名|外部ID")に持たせ、ワークフロー側でこの
ファイルをリポジトリにコミットし直すことで、実行のたびに新しいGitHub Actions
ランナーが立ち上がっても「既に通知済みかどうか」を判定できるようにしている。
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_sources_config, settings  # noqa: E402
from app.notify.line import notify_new_items  # noqa: E402
from app.sources.base import is_excluded, match_keywords  # noqa: E402
from app.sources.registry import build_source  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEN_FILE = DATA_DIR / "seen.txt"
# GitHub Actionsのcronは短い間隔(例: 5分)で起動する一方、ソースごとに
# config/sources.yaml の poll_interval_sec を守ってアクセス頻度を抑えるため、
# 各ソースを最後に巡回した時刻をここに記録しておく。
LAST_FETCH_FILE = DATA_DIR / "last_fetch.json"
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


def load_seen() -> list[str]:
    """data/seen.txt をファイルに書かれている順番のまま読み込む。

    set() の反復順はプロセスごとに変わり得るため、順序の情報源には使わない。
    ファイルの行順そのものを「古い順」の記録として扱うことで、次回保存時に
    実際に増減した分だけが差分に出るようにする(実行のたびに全体の並びが
    入れ替わって無意味な差分がコミットされるのを防ぐ)。
    """
    if not SEEN_FILE.exists():
        return []
    return [line for line in SEEN_FILE.read_text(encoding="utf-8").splitlines() if line]


def save_seen(seen_order: list[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    trimmed = seen_order[-MAX_SEEN_LINES:]
    SEEN_FILE.write_text("\n".join(trimmed) + "\n", encoding="utf-8")


def load_last_fetch() -> dict[str, str]:
    if not LAST_FETCH_FILE.exists():
        return {}
    try:
        return json.loads(LAST_FETCH_FILE.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def save_last_fetch(last_fetch: dict[str, str]) -> None:
    LAST_FETCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_FETCH_FILE.write_text(json.dumps(last_fetch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_due(name: str, interval_sec: int, last_fetch: dict[str, str]) -> bool:
    last = last_fetch.get(name)
    if not last:
        return True
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
    return elapsed >= interval_sec


def main() -> None:
    config = load_sources_config()
    default_keywords = config.get("default_keywords", [])
    default_exclude = config.get("default_exclude_keywords", [])

    seen_order = load_seen()
    seen = set(seen_order)
    last_fetch = load_last_fetch()
    new_items: list[NotifiableItem] = []

    for src in config.get("sources", []):
        if not src.get("enabled"):
            continue
        name = src["name"]
        keywords = src.get("keywords") or default_keywords
        exclude_keywords = src.get("exclude_keywords") or default_exclude
        match_all = bool(src.get("match_all"))
        interval_sec = int(src.get("poll_interval_sec") or settings.default_poll_interval_sec)

        if not is_due(name, interval_sec, last_fetch):
            logger.info("%s: 前回巡回から %d 秒経っていないためスキップします", name, interval_sec)
            continue

        try:
            source = build_source(name, src["type"], src)
            fetched_items = source.fetch(keywords)
        except Exception:
            logger.exception("巡回中にエラーが発生しました: %s", name)
            continue

        last_fetch[name] = datetime.now(timezone.utc).isoformat()

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
    save_last_fetch(last_fetch)


if __name__ == "__main__":
    main()
