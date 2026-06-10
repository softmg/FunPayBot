from decimal import Decimal

from app.parser import LotSearchFilters, extract_warranty, parse_category_paths, parse_lots


def test_parse_lots_applies_filters() -> None:
    html = """
    <a class="tc-item" href="/lots/1355/1/">Steam account 45 руб. 12 отзывов гарантия: 24 часа</a>
    <a class="tc-item" href="/lots/1355/2/">Steam blocked 20 руб. 40 отзывов гарантия: 1 час</a>
    <a class="tc-item" href="/lots/1355/3/">Steam account 90 руб. 1 отзыв гарантия: 24 часа</a>
    """

    lots = parse_lots(
        html,
        LotSearchFilters(
            query="steam account",
            max_price=Decimal("50"),
            min_reviews=10,
            forbidden_words=("blocked",),
        ),
    )

    assert len(lots) == 1
    assert lots[0]["url"].endswith("/lots/1355/1/")
    assert lots[0]["price"] == "45"
    assert lots[0]["reviews"] == 12


def test_extract_warranty_detects_russian_text() -> None:
    assert extract_warranty("Описание. Гарантия: 24 часа после покупки.") == "Гарантия: 24 часа после покупки"


def test_parse_category_paths_matches_relevant_games() -> None:
    html = """
    <div class="promo-game-item">
      <div class="game-title"><a href="https://funpay.com/en/lots/4092/">Gemini</a></div>
      <ul><li><a href="https://funpay.com/en/lots/4093/">Services</a></li></ul>
    </div>
    <div class="promo-game-item">
      <div class="game-title"><a href="https://funpay.com/en/lots/1355/">ChatGPT</a></div>
    </div>
    """

    assert parse_category_paths(html, "Gemini api") == ["lots/4092/", "lots/4093/"]
