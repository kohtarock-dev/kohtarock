from app.sources.rss_generic import _extract_price


def test_extracts_labeled_price_across_html_tags():
    html = "<strong>価格: </strong>\n    65000\n</p>"
    assert _extract_price(html) == 65000.0


def test_ignores_unrelated_amounts_without_label():
    html = "<p>1500円以上で送料無料キャンペーン実施中</p>"
    assert _extract_price(html) is None


def test_no_price_label_returns_none():
    html = "<p>このロッドはとても良く曲がります</p>"
    assert _extract_price(html) is None


def test_empty_html_returns_none():
    assert _extract_price("") is None
