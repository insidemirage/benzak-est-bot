from dataclasses import dataclass
from math import cos, radians
from urllib.parse import urlencode


EARTH_KM_PER_DEGREE = 111.32
DEFAULT_RADIUS_KM = 5.0
STATIONS_API_URL = "https://toplivo.tbank.ru/api/v1/stations"


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


def format_coordinate(value: float) -> str:
    return f"{value:.14f}".rstrip("0").rstrip(".")

