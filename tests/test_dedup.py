import pytest
from sqlalchemy.exc import IntegrityError

from app.db import Item, SessionLocal, init_db


def test_duplicate_source_external_id_is_rejected():
    init_db()
    session = SessionLocal()
    try:
        session.query(Item).filter(Item.source_name == "test_src_dedup").delete()
        session.commit()

        session.add(
            Item(source_name="test_src_dedup", source_type="rss", external_id="abc", title="t1", url="http://x")
        )
        session.commit()

        session.add(
            Item(source_name="test_src_dedup", source_type="rss", external_id="abc", title="t2", url="http://y")
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.query(Item).filter(Item.source_name == "test_src_dedup").delete()
        session.commit()
        session.close()


def test_different_sources_can_share_external_id():
    init_db()
    session = SessionLocal()
    try:
        session.query(Item).filter(Item.external_id == "shared-id").delete()
        session.commit()

        session.add(
            Item(source_name="source_a", source_type="rss", external_id="shared-id", title="t1", url="http://x")
        )
        session.add(
            Item(source_name="source_b", source_type="rss", external_id="shared-id", title="t2", url="http://y")
        )
        session.commit()

        count = session.query(Item).filter(Item.external_id == "shared-id").count()
        assert count == 2
    finally:
        session.query(Item).filter(Item.external_id == "shared-id").delete()
        session.commit()
        session.close()
