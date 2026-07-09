import re
from dataclasses import dataclass
from math import cos, radians
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse


EARTH_KM_PER_DEGREE = 111.32
DEFAULT_RADIUS_KM = 5.0
STATIONS_API_URL = "https://toplivo.tbank.ru/api/v1/stations"
URL_RE = re.compile(r"(?:https?://|yandexnavi://|geo:)[^\s<>\"]+")
COORDINATE_PAIR_RE = re.compile(
    r"(?P<first>[+-]?\d{1,3}(?:\.\d+)?)\s*,\s*(?P<second>[+-]?\d{1,3}(?:\.\d+)?)"
)


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


def build_bounding_box(coordinates: Coordinates, radius_km: float = DEFAULT_RADIUS_KM) -> BoundingBox:
    lat_delta = radius_km / EARTH_KM_PER_DEGREE
    lon_delta = radius_km / (EARTH_KM_PER_DEGREE * cos(radians(coordinates.latitude)))

    return BoundingBox(
        min_lat=coordinates.latitude - lat_delta,
        max_lat=coordinates.latitude + lat_delta,
        min_lon=coordinates.longitude - lon_delta,
        max_lon=coordinates.longitude + lon_delta,
    )


def build_stations_url(coordinates: Coordinates, radius_km: float = DEFAULT_RADIUS_KM) -> str:
    bbox = build_bounding_box(coordinates, radius_km)
    query = urlencode(
        {
            "minLat": format_coordinate(bbox.min_lat),
            "maxLat": format_coordinate(bbox.max_lat),
            "minLon": format_coordinate(bbox.min_lon),
            "maxLon": format_coordinate(bbox.max_lon),
        }
    )

    return f"{STATIONS_API_URL}?{query}"


def parse_shared_location_text(text: str) -> Optional[Coordinates]:
    for url in extract_urls(text):
        coordinates = parse_shared_location_url(url)
        if coordinates is not None:
            return coordinates

    return None


def extract_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(".,);]") for match in URL_RE.finditer(text)]


def parse_shared_location_url(url: str) -> Optional[Coordinates]:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if hostname.endswith("2gis.ru"):
        return parse_2gis_coordinates(parsed.path)

    if (
        hostname.endswith("yandex.ru")
        or hostname.endswith("yandex.com")
        or parsed.scheme == "yandexnavi"
    ):
        return parse_yandex_coordinates(url)

    if parsed.scheme == "geo":
        return parse_geo_coordinates(url)

    return None


def parse_2gis_coordinates(path: str) -> Optional[Coordinates]:
    return parse_coordinate_pair(path, first_is_longitude=True)


def parse_yandex_coordinates(url: str) -> Optional[Coordinates]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    for key in ("ll", "pt", "whatshere[point]", "zll"):
        for value in query.get(key, []):
            coordinates = parse_coordinate_pair(value, first_is_longitude=True)
            if coordinates is not None:
                return coordinates

    for lat_key, lon_key in (
        ("lat_to", "lon_to"),
        ("lat_from", "lon_from"),
        ("lat", "lon"),
        ("latitude", "longitude"),
    ):
        coordinates = parse_coordinate_query_params(query, lat_key, lon_key)
        if coordinates is not None:
            return coordinates

    return parse_coordinate_pair(parsed.path, first_is_longitude=True)


def parse_geo_coordinates(url: str) -> Optional[Coordinates]:
    parsed = urlparse(url)
    coordinates = parse_coordinate_pair(parsed.path, first_is_longitude=False)
    if coordinates is not None:
        return coordinates

    return parse_coordinate_pair(parsed.query, first_is_longitude=False)


def parse_coordinate_query_params(
    query: dict[str, list[str]],
    lat_key: str,
    lon_key: str,
) -> Optional[Coordinates]:
    if lat_key not in query or lon_key not in query:
        return None

    try:
        latitude = float(query[lat_key][0])
        longitude = float(query[lon_key][0])
    except (TypeError, ValueError):
        return None

    return build_coordinates(latitude=latitude, longitude=longitude)


def parse_coordinate_pair(value: str, first_is_longitude: bool) -> Optional[Coordinates]:
    match = COORDINATE_PAIR_RE.search(value)
    if match is None:
        return None

    first = float(match.group("first"))
    second = float(match.group("second"))
    if first_is_longitude:
        return build_coordinates(latitude=second, longitude=first)

    return build_coordinates(latitude=first, longitude=second)


def build_coordinates(latitude: float, longitude: float) -> Optional[Coordinates]:
    if not -90 <= latitude <= 90:
        return None

    if not -180 <= longitude <= 180:
        return None

    return Coordinates(latitude=latitude, longitude=longitude)


def format_coordinate(value: float) -> str:
    return f"{value:.14f}".rstrip("0").rstrip(".")
