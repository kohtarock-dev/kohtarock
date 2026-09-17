from datetime import date, timedelta

from app.sources.sitemap_diff import parse_sitemap


def _sitemap_xml(*, recent_loc: str, old_loc: str, top_page_loc: str) -> bytes:
    today = date.today().isoformat()
    old = (date.today() - timedelta(days=30)).isoformat()
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{recent_loc}</loc><lastmod>{today}</lastmod></url>
  <url><loc>{old_loc}</loc><lastmod>{old}</lastmod></url>
  <url><loc>{top_page_loc}</loc><lastmod>{today}</lastmod></url>
</urlset>"""
    return xml.encode("utf-8")


def test_only_recent_product_urls_are_returned():
    xml = _sitemap_xml(
        recent_loc="https://example.com/item?uid=1",
        old_loc="https://example.com/item?uid=2",
        top_page_loc="https://example.com/",
    )
    items = parse_sitemap(xml, recent_days=3, shop_name="テスト店")

    assert len(items) == 1
    assert items[0].url == "https://example.com/item?uid=1"
    assert items[0].price is None
    assert items[0].shop_name == "テスト店"


def test_old_items_are_excluded():
    xml = _sitemap_xml(
        recent_loc="https://example.com/item?uid=1",
        old_loc="https://example.com/item?uid=2",
        top_page_loc="https://example.com/",
    )
    items = parse_sitemap(xml, recent_days=3, shop_name="テスト店")
    urls = [item.url for item in items]
    assert "https://example.com/item?uid=2" not in urls


def test_top_page_without_query_is_excluded():
    xml = _sitemap_xml(
        recent_loc="https://example.com/item?uid=1",
        old_loc="https://example.com/item?uid=2",
        top_page_loc="https://example.com/",
    )
    items = parse_sitemap(xml, recent_days=3, shop_name="テスト店")
    urls = [item.url for item in items]
    assert "https://example.com/" not in urls


def test_malformed_xml_returns_empty():
    assert parse_sitemap(b"not xml", recent_days=3, shop_name="テスト店") == []
