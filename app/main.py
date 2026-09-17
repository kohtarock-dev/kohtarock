"""FastAPI アプリケーション本体。"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.config import BASE_DIR, load_sources_config, settings
from app.db import Item, SessionLocal, init_db
from app.scheduler import run_all_sources_once, scheduler, setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    setup_scheduler()
    scheduler.start()
    logger.info("スケジューラを起動しました")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="釣具せどり 入荷情報スクレイパー", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/")
def index(request: Request, q: str = "", source: str = "", favorite: bool = False):
    session = SessionLocal()
    try:
        stmt = select(Item).order_by(Item.first_seen_at.desc())
        if q:
            stmt = stmt.where(Item.title.ilike(f"%{q}%"))
        if source:
            stmt = stmt.where(Item.source_name == source)
        if favorite:
            stmt = stmt.where(Item.is_favorite.is_(True))
        items = session.execute(stmt.limit(200)).scalars().all()

        source_names = session.execute(select(Item.source_name).distinct()).scalars().all()
    finally:
        session.close()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "items": items,
            "q": q,
            "selected_source": source,
            "favorite_only": favorite,
            "source_names": sorted(source_names),
            "line_enabled": settings.line_enabled,
        },
    )


@app.post("/items/{item_id}/favorite")
def toggle_favorite(item_id: int, next: str = Form("/")):
    session = SessionLocal()
    try:
        item = session.get(Item, item_id)
        if item:
            item.is_favorite = not item.is_favorite
            session.commit()
    finally:
        session.close()
    return RedirectResponse(url=next, status_code=303)


@app.get("/sources")
def sources_page(request: Request):
    config = load_sources_config()
    session = SessionLocal()
    try:
        counts = dict(
            session.execute(select(Item.source_name, func.count(Item.id)).group_by(Item.source_name)).all()
        )
    finally:
        session.close()

    return templates.TemplateResponse(
        "sources.html",
        {
            "request": request,
            "sources": config.get("sources", []),
            "default_keywords": config.get("default_keywords", []),
            "counts": counts,
        },
    )


@app.post("/refresh")
def refresh():
    """手動で全ソースを即時巡回する(時間がかかるためバックグラウンドスレッドで実行)。"""
    thread = threading.Thread(target=run_all_sources_once, daemon=True)
    thread.start()
    return RedirectResponse(url="/?refreshing=1", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
