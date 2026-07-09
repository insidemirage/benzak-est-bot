import html
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse

from app.geo import Coordinates, build_coordinates, extract_urls, parse_shared_location_text


YANDEX_COORDINATES_RE = re.compile(
    r'"coordinates"\s*:\s*\[\s*(?P<longitude>[+-]?\d{1,3}(?:\.\d+)?)\s*,\s*'
    r'(?P<latitude>[+-]?\d{1,3}(?:\.\d+)?)\s*\]'
)
YANDEX_POINT_RE = re.compile(
    r'"(?:ll|point)"\s*:\s*"(?P<longitude>[+-]?\d{1,3}(?:\.\d+)?)\s*,\s*'
    r'(?P<latitude>[+-]?\d{1,3}(?:\.\d+)?)"'
)


@dataclass(frozen=True)
class ResolvedPage:
    final_url: str
    text: str


PageFetcher = Callable[[str], Awaitable[ResolvedPage]]


async def resolve_shared_location_text(
    text: str,
    fetch_page: Optional[PageFetcher] = None,
) -> Optional[Coordinates]:
    coordinates = parse_shared_location_text(text)
    if coordinates is not None:
        return coordinates

    fetch = fetch_page or fetch_url
    for url in extract_yandex_urls(text):
        try:
            page = await fetch(url)
        except Exception:
            logging.exception("Failed to resolve shared Yandex location")
            continue

        coordinates = parse_shared_location_text(page.final_url)
        if coordinates is not None:
            return coordinates

        coordinates = parse_yandex_page_coordinates(page.text)
        if coordinates is not None:
            return coordinates

    return None


def extract_yandex_urls(text: str) -> list[str]:
    urls = []
    for url in extract_urls(text):
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if (
            parsed.scheme == "yandexnavi"
            or hostname.endswith("yandex.ru")
            or hostname.endswith("yandex.com")
        ):
            urls.append(url)

    return urls


def parse_yandex_page_coordinates(text: str) -> Optional[Coordinates]:
    decoded_text = html.unescape(text)
    for pattern in (YANDEX_COORDINATES_RE, YANDEX_POINT_RE):
        match = pattern.search(decoded_text)
        if match is None:
            continue

        return build_coordinates(
            latitude=float(match.group("latitude")),
            longitude=float(match.group("longitude")),
        )

    return None


async def fetch_url(url: str) -> ResolvedPage:
    from aiohttp import ClientSession

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; BenzakBot/1.0; "
            "+https://t.me/benzakest_bot)"
        ),
    }
    async with ClientSession(headers=headers) as session:
        async with session.get(url, allow_redirects=True) as response:
            response.raise_for_status()
            return ResolvedPage(final_url=str(response.url), text=await response.text())
