from app.sources.base import match_keywords


def test_matches_included_keyword():
    assert match_keywords("ロデオクラフト ノアサイト 61", ["ロデオクラフト"], []) == "ロデオクラフト"


def test_no_match_returns_none():
    assert match_keywords("普通のシーバスルアー", ["ロデオクラフト", "エリアトラウト"], []) is None


def test_excluded_keyword_blocks_match():
    assert (
        match_keywords("エリアトラウト ロッド 中古 ジャンク", ["エリアトラウト"], ["中古 ジャンク"])
        is None
    )


def test_empty_title_returns_none():
    assert match_keywords("", ["エリアトラウト"], []) is None


def test_case_insensitive_match():
    assert match_keywords("VALKEIN スプーン", ["valkein"], []) == "valkein"
