import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Iterable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.config import settings


@dataclass(frozen=True)
class LotSearchFilters:
    query: str
    max_price: Decimal | None = None
    min_reviews: int = 0
    forbidden_words: tuple[str, ...] = ()


def parse_price(text: str) -> Decimal | None:
    match = re.search(r"(\d+(?:[\s.,]\d+)*)", text.replace("\xa0", " "))
    if not match:
        return None
    normalized = match.group(1).replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_reviews(text: str) -> int:
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
    candidates: Iterable = soup.select("a[href*='/lots/'], a[href*='/orders/'], a.tc-item")
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
        price = parse_price(text)
        reviews = parse_reviews(text)
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


async def fetch_category_html(client: httpx.AsyncClient) -> str:
    url = urljoin(settings.funpay_base_url, settings.funpay_category_path)
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    return response.text


async def search_lots(filters: LotSearchFilters) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        html = await fetch_category_html(client)
    return parse_lots(html, filters)


async def fetch_funpay_warranty(lot_url: str) -> str | None:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(lot_url, follow_redirects=True)
        response.raise_for_status()
    text = normalize_text(BeautifulSoup(response.text, "html.parser").get_text(" "))
    return extract_warranty(text)

