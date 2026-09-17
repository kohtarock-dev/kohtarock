"""各ソースを設定された間隔で巡回し、新着アイテムをDB保存 + LINE通知する。"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.exc import IntegrityError

from app.config import load_sources_config, settings
from app.db import Item, SessionLocal
from app.notify.line import notify_new_items
from app.sources.base import match_keywords
from app.sources.registry import build_source

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Tokyo")


def poll_source(name: str, source_type: str, config: dict, keywords: list[str], exclude_keywords: list[str]) -> None:
    logger.info("巡回開始: %s (%s)", name, source_type)
    try:
        source = build_source(name, source_type, config)
        fetched_items = source.fetch(keywords)
    except Exception:
        logger.exception("巡回中にエラーが発生しました: %s", name)
        return

    new_items: list[Item] = []
    session = SessionLocal()
    try:
        for fetched in fetched_items:
            matched_keyword = match_keywords(fetched.title, keywords, exclude_keywords)
            if not matched_keyword:
                continue

            exists = (
                session.query(Item.id)
                .filter(Item.source_name == name, Item.external_id == fetched.external_id)
                .first()
            )
            if exists:
                continue

            item = Item(
                source_name=name,
                source_type=source_type,
                external_id=fetched.external_id,
                title=fetched.title,
                price=fetched.price,
                url=fetched.url,
                image_url=fetched.image_url,
                shop_name=fetched.shop_name or name,
                condition=fetched.condition,
                matched_keyword=matched_keyword,
                notified=False,
            )
            session.add(item)
            try:
                session.flush()
            except IntegrityError:
                # 並行実行やAPI応答の重複によるユニーク制約違反は無視して次へ
                session.rollback()
                continue
            new_items.append(item)

        if new_items:
            session.commit()
            logger.info("%s: 新着 %d 件を検出しました", name, len(new_items))
            try:
                notify_new_items(new_items)
                for item in new_items:
                    item.notified = True
                session.commit()
            except Exception:
                logger.exception("LINE通知処理でエラーが発生しました")
        else:
            session.commit()
    finally:
        session.close()


def setup_scheduler() -> BackgroundScheduler:
    config = load_sources_config()
    default_keywords = config.get("default_keywords", [])
    default_exclude = config.get("default_exclude_keywords", [])

    for src in config.get("sources", []):
        if not src.get("enabled"):
            continue
        name = src["name"]
        source_type = src["type"]
        interval = int(src.get("poll_interval_sec") or settings.default_poll_interval_sec)
        keywords = src.get("keywords") or default_keywords
        exclude_keywords = src.get("exclude_keywords") or default_exclude

        scheduler.add_job(
            poll_source,
            trigger=IntervalTrigger(seconds=interval),
            args=[name, source_type, src, keywords, exclude_keywords],
            id=f"poll_{name}",
            replace_existing=True,
            next_run_time=None,  # 起動直後ではなく最初の interval 経過後に実行
            max_instances=1,
            coalesce=True,
        )
        logger.info("ソースを登録しました: %s (%s, %d秒毎)", name, source_type, interval)

    return scheduler


def run_all_sources_once() -> None:
    """全ての有効ソースを即時に1回だけ巡回する(手動更新ボタン用)。"""
    config = load_sources_config()
    default_keywords = config.get("default_keywords", [])
    default_exclude = config.get("default_exclude_keywords", [])

    for src in config.get("sources", []):
        if not src.get("enabled"):
            continue
        keywords = src.get("keywords") or default_keywords
        exclude_keywords = src.get("exclude_keywords") or default_exclude
        poll_source(src["name"], src["type"], src, keywords, exclude_keywords)
