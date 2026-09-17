from dataclasses import dataclass

from app.notify.line import ITEMS_PER_MESSAGE, _build_batch_message, _format_item


@dataclass
class FakeItem:
    source_name: str
    title: str
    price: float | None
    url: str
    shop_name: str | None
    matched_keyword: str | None


def make_item(i: int) -> FakeItem:
    return FakeItem(
        source_name="テスト店",
        title=f"テスト商品{i}",
        price=1000 + i,
        url=f"https://example.com/{i}",
        shop_name="テスト店",
        matched_keyword=None,
    )


def test_format_item_contains_title_price_url():
    item = make_item(1)
    text = _format_item(item)
    assert "テスト商品1" in text
    assert "1,001円" in text
    assert "https://example.com/1" in text


def test_format_item_handles_missing_price():
    item = make_item(1)
    item.price = None
    text = _format_item(item)
    assert "価格不明" in text


def test_build_batch_message_includes_count_and_all_items():
    items = [make_item(i) for i in range(3)]
    text = _build_batch_message(items)
    assert "【新着 3件】" in text
    for item in items:
        assert item.title in text


def test_items_per_message_keeps_text_well_under_line_limit():
    items = [make_item(i) for i in range(ITEMS_PER_MESSAGE)]
    text = _build_batch_message(items)
    assert len(text) < 5000
