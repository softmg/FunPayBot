from decimal import Decimal

import httpx
import pytest

from app.parser import (
    LotSearchFilters,
    extract_lot_descriptions,
    extract_warranty,
    extract_warranty_from_texts,
    fetch_html,
    fetch_lot_details,
    filters_for_category,
    parse_category_matches,
    parse_category_paths,
    parse_lots,
)


def test_parse_lots_applies_filters() -> None:
    html = """
    <a class="tc-item" href="/lots/1355/1/">
      <div class="media-body">
        <div class="media-user-reviews">12 отзывов</div>
      </div>
      <div class="tc-price" data-s="45"><div>45 руб.</div></div>
      Steam account гарантия: 24 часа
    </a>
    <a class="tc-item" href="/lots/1355/2/">
      <div class="media-body">
        <div class="media-user-reviews">40 отзывов</div>
      </div>
      <div class="tc-price" data-s="20"><div>20 руб.</div></div>
      Steam blocked гарантия: 1 час
    </a>
    <a class="tc-item" href="/lots/1355/3/">
      <div class="media-body">
        <div class="media-user-reviews">1 отзыв</div>
      </div>
      <div class="tc-price" data-s="90"><div>90 руб.</div></div>
      Steam account гарантия: 24 часа
    </a>
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


def test_parse_lots_uses_dedicated_price_block_when_title_contains_numbers() -> None:
    html = """
    <a class="tc-item" href="/lots/1355/1/">
      <div class="media-body">
        <div class="media-user-reviews">114 отзывов</div>
      </div>
      <div class="tc-price" data-s="1490"><div>1490 ₽</div></div>
      💎⭐️CHATGPT PLUS 5.5 + CODEX 25 ДНЕЙ⭐️
    </a>
    """

    lots = parse_lots(html, LotSearchFilters(query="chatgpt"))

    assert len(lots) == 1
    assert lots[0]["price"] == "1490"
    assert lots[0]["reviews"] == 114


def test_extract_warranty_detects_russian_text() -> None:
    assert extract_warranty("Описание. Гарантия: 24 часа после покупки.") == "Гарантия: 24 часа после покупки"


def test_extract_lot_descriptions_reads_detailed_description() -> None:
    html = """
    <div class="param-item"><h5>Short description</h5><div>Short summary</div></div>
    <div class="param-item"><h5>Detailed description</h5><div>ГАРАНТИЯ ВЕСЬ СРОК 🟢, С подпиской</div></div>
    """

    descriptions = extract_lot_descriptions(html)

    assert descriptions["short_description"] == "Short summary"
    assert descriptions["detailed_description"] == "ГАРАНТИЯ ВЕСЬ СРОК 🟢, С подпиской"


def test_extract_warranty_prefers_detailed_description() -> None:
    warranty = extract_warranty_from_texts(None, "Some other text", "ГАРАНТИЯ ВЕСЬ СРОК 🟢, С подпиской")

    assert warranty == "ГАРАНТИЯ ВЕСЬ СРОК 🟢, С подпиской"


def test_extract_warranty_falls_back_to_title() -> None:
    warranty = extract_warranty_from_texts(None, None, "Лот. Гарантия: 12 часов")

    assert warranty == "Гарантия: 12 часов"


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


def test_category_matches_prioritize_title_hits() -> None:
    html = """
    <div class="promo-game-item">
      <div class="game-title"><a href="https://funpay.com/en/lots/100/">Some API Game</a></div>
    </div>
    <div class="promo-game-item">
      <div class="game-title"><a href="https://funpay.com/en/lots/200/">Gemini</a></div>
      <ul><li><a href="https://funpay.com/en/lots/201/">Services</a></li></ul>
    </div>
    """

    matches = parse_category_matches(html, "Gemini API")

    assert [match.path for match in matches] == ["lots/200/", "lots/201/", "lots/100/"]
    assert matches[0].matched_terms == frozenset({"gemini"})


def test_filters_for_category_removes_category_terms_from_lot_query() -> None:
    filters = filters_for_category(
        LotSearchFilters(query="Gemini API", max_price=Decimal("10"), min_reviews=2, forbidden_words=("bad",)),
        frozenset({"gemini"}),
    )

    assert filters.query == "api"
    assert filters.max_price == Decimal("10")
    assert filters.min_reviews == 2
    assert filters.forbidden_words == ("bad",)


@pytest.mark.asyncio
async def test_fetch_lot_details_returns_empty_details_on_429() -> None:
    request = httpx.Request("GET", "https://funpay.com/lots/offer?id=1")
    response = httpx.Response(429, request=request)

    class FakeClient:
        async def get(self, lot_url: str, follow_redirects: bool):
            raise httpx.HTTPStatusError("Too Many Requests", request=request, response=response)

    details = await fetch_lot_details(FakeClient(), "https://funpay.com/lots/offer?id=1")

    assert details == {"short_description": None, "detailed_description": None}


@pytest.mark.asyncio
async def test_fetch_html_retries_timeouts() -> None:
    class FakeResponse:
        text = "<html>ok</html>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def get(self, url: str, follow_redirects: bool):
            self.calls += 1
            if self.calls < 3:
                raise httpx.ConnectTimeout("timed out")
            return FakeResponse()

    client = FakeClient()
    html = await fetch_html(client, "lots/1355/")

    assert html == "<html>ok</html>"
    assert client.calls == 3
