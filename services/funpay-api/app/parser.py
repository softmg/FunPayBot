import asyncio
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Iterable, Literal
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LotSearchFilters:
    query: str
    max_price: Decimal | None = None
    min_reviews: int = 0
    forbidden_words: tuple[str, ...] = ()


@dataclass(frozen=True)
class CategoryMatch:
    path: str
    matched_terms: frozenset[str]
    score: int


SearchScope = Literal["category", "site"]

PAGE_DESCRIPTION_HEADINGS = {
    "short description",
    "краткое описание",
    "подробное описание",
    "detailed description",
}
LOT_DETAILS_CONCURRENCY = 5


class FunPayUpstreamTimeoutError(RuntimeError):
    pass


def parse_price(text: str) -> Decimal | None:
    match = re.search(r"(\d+(?:[\s.,]\d+)*)", text.replace("\xa0", " "))
    if not match:
        return None
    normalized = match.group(1).replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def extract_price(node: BeautifulSoup, text: str) -> Decimal | None:
    price_node = node.select_one(".tc-price")
    if price_node is not None:
        data_s = price_node.get("data-s")
        if data_s:
            try:
                return Decimal(str(data_s))
            except InvalidOperation:
                pass

        price_text = normalize_text(price_node.get_text(" "))
        if price_text:
            parsed = parse_price(price_text)
            if parsed is not None:
                return parsed

    return parse_price(text)


def extract_reviews(node: BeautifulSoup, text: str) -> int:
    reviews_node = node.select_one(".media-user-reviews")
    if reviews_node is not None:
        digits = "".join(ch for ch in reviews_node.get_text(" ") if ch.isdigit())
        if digits:
            return int(digits)

    match = re.search(r"(\d+)\s*(?:отзыв|review)", text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_warranty(text: str) -> str | None:
    match = re.search(
        r"(?:гарант(?:ия|ии|ию)?|warranty)\s*[:\-]?\s*([^.。\n\r]{1,120})",
        text,
        re.IGNORECASE,
    )
    return normalize_text(match.group(0)) if match else None


def extract_lot_descriptions(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    descriptions: dict[str, str | None] = {
        "short_description": None,
        "detailed_description": None,
    }

    for param in soup.select(".param-item"):
        heading = param.find(["h5", "div"])
        value = param.find("div")
        if heading is None or value is None:
            continue

        heading_text = normalize_text(heading.get_text(" ")).lower()
        if heading_text not in PAGE_DESCRIPTION_HEADINGS:
            continue

        value_text = normalize_text(value.get_text(" "))
        if not value_text:
            continue

        if heading_text in {"short description", "краткое описание"}:
            descriptions["short_description"] = value_text
        elif heading_text in {"подробное описание", "detailed description"}:
            descriptions["detailed_description"] = value_text

    return descriptions


def extract_warranty_from_texts(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        warranty = extract_warranty(text)
        if warranty:
            return warranty
    return None


def lot_matches(text: str, filters: LotSearchFilters, price: Decimal | None, reviews: int) -> bool:
    lowered = text.lower()
    terms = [term for term in filters.query.lower().split() if term]
    if terms and not all(term in lowered for term in terms):
        return False
    if filters.max_price is not None and (price is None or price > filters.max_price):
        return False
    if reviews < filters.min_reviews:
        return False
    if any(word.lower() in lowered for word in filters.forbidden_words):
        return False
    return True


def parse_lots(html: str, filters: LotSearchFilters) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: Iterable = soup.select("a.tc-item[href]")
    lots: list[dict] = []
    seen: set[str] = set()

    for node in candidates:
        href = node.get("href")
        if not href:
            continue
        url = urljoin(settings.funpay_base_url, href)
        if url in seen:
            continue
        text = normalize_text(node.get_text(" "))
        if not text:
            continue
        price = extract_price(node, text)
        reviews = extract_reviews(node, text)
        if not lot_matches(text, filters, price, reviews):
            continue
        seen.add(url)
        lots.append(
            {
                "title": text[:220],
                "url": url,
                "price": str(price) if price is not None else None,
                "reviews": reviews,
                "warranty": extract_warranty(text),
            }
        )

    return lots


def normalize_lot_path(href: str) -> str:
    parsed = urlparse(urljoin(settings.funpay_base_url, href))
    path = parsed.path.lstrip("/")
    if path.startswith("en/"):
        path = path[3:]
    return path


def parse_category_matches(html: str, query: str, limit: int = 20) -> list[CategoryMatch]:
    soup = BeautifulSoup(html, "html.parser")
    terms = [term for term in query.lower().split() if term]
    matches: list[CategoryMatch] = []
    best_by_path: dict[str, CategoryMatch] = {}

    for node in soup.select(".promo-game-item"):
        title = normalize_text(node.select_one(".game-title").get_text(" ") if node.select_one(".game-title") else "")
        text = normalize_text(node.get_text(" "))
        lowered_title = title.lower()
        lowered_text = text.lower()
        title_terms = {term for term in terms if term in lowered_title}
        text_terms = {term for term in terms if term in lowered_text}
        if terms and not text_terms:
            continue
        score = len(title_terms) * 4 + len(text_terms)
        if terms and terms[0] in title_terms:
            score += 2

        for link in node.select("a[href*='/lots/']"):
            href = link.get("href")
            if not href:
                continue
            path = normalize_lot_path(href)
            current = best_by_path.get(path)
            candidate = CategoryMatch(path=path, matched_terms=frozenset(text_terms), score=score)
            if current is None or candidate.score > current.score:
                best_by_path[path] = candidate

    matches = sorted(best_by_path.values(), key=lambda match: match.score, reverse=True)
    return matches[:limit]


def parse_category_paths(html: str, query: str, limit: int = 20) -> list[str]:
    return [match.path for match in parse_category_matches(html, query, limit=limit)]


def filters_for_category(filters: LotSearchFilters, category_terms: frozenset[str]) -> LotSearchFilters:
    lot_terms = [term for term in filters.query.lower().split() if term and term not in category_terms]
    return LotSearchFilters(
        query=" ".join(lot_terms),
        max_price=filters.max_price,
        min_reviews=filters.min_reviews,
        forbidden_words=filters.forbidden_words,
    )


async def fetch_html(client: httpx.AsyncClient, path: str) -> str:
    url = urljoin(settings.funpay_base_url, path)
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise FunPayUpstreamTimeoutError(f"Timed out while fetching FunPay page: {url}") from exc
    return response.text


async def fetch_lot_details(client: httpx.AsyncClient, lot_url: str) -> dict[str, str | None]:
    empty_details = {"short_description": None, "detailed_description": None}
    try:
        response = await client.get(lot_url, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch FunPay lot details for %s: %s", lot_url, exc)
        return empty_details
    return extract_lot_descriptions(response.text)


async def fetch_lot_details_limited(
    client: httpx.AsyncClient,
    lot_url: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, str | None]:
    async with semaphore:
        return await fetch_lot_details(client, lot_url)


async def search_lots(filters: LotSearchFilters, scope: SearchScope = "category") -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        if scope == "category":
            html = await fetch_html(client, settings.funpay_category_path)
            lots = parse_lots(html, filters)
        else:
            index_html = await fetch_html(client, "en/")
            category_matches = parse_category_matches(index_html, filters.query)
            if not category_matches:
                return []

            lots = []
            seen: set[str] = set()
            for match in category_matches:
                html = await fetch_html(client, match.path)
                category_filters = filters_for_category(filters, match.matched_terms)
                for lot in parse_lots(html, category_filters):
                    if lot["url"] in seen:
                        continue
                    seen.add(lot["url"])
                    lots.append(lot)

        if not lots:
            return []

        semaphore = asyncio.Semaphore(LOT_DETAILS_CONCURRENCY)
        details = await asyncio.gather(
            *(fetch_lot_details_limited(client, lot["url"], semaphore) for lot in lots)
        )
        for lot, lot_details in zip(lots, details, strict=True):
            lot["short_description"] = lot_details["short_description"]
            lot["detailed_description"] = lot_details["detailed_description"]
            lot["warranty"] = extract_warranty_from_texts(
                lot_details["detailed_description"],
                lot_details["short_description"],
                lot["warranty"],
            )
        return lots


async def fetch_funpay_warranty(lot_url: str, title: str | None = None) -> str | None:
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(lot_url, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            return extract_warranty_from_texts(title)
    descriptions = extract_lot_descriptions(response.text)
    return extract_warranty_from_texts(
        descriptions["detailed_description"],
        descriptions["short_description"],
        title,
    )
