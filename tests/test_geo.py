import unittest
from urllib.parse import parse_qs, urlparse

from app.geo import Coordinates, build_bounding_box, build_stations_url, parse_shared_location_text


class GeoTest(unittest.TestCase):
    def test_build_bounding_box_contains_source_coordinates(self) -> None:
        coordinates = Coordinates(latitude=10.0, longitude=20.0)

        bbox = build_bounding_box(coordinates, radius_km=5)

        self.assertLess(bbox.min_lat, coordinates.latitude)
        self.assertLess(coordinates.latitude, bbox.max_lat)
        self.assertLess(bbox.min_lon, coordinates.longitude)
        self.assertLess(coordinates.longitude, bbox.max_lon)

    def test_build_stations_url_uses_tbank_bbox_parameters(self) -> None:
        coordinates = Coordinates(latitude=10.0, longitude=20.0)

        url = build_stations_url(coordinates, radius_km=5)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertEqual("https", parsed.scheme)
        self.assertEqual("toplivo.tbank.ru", parsed.netloc)
        self.assertEqual("/api/v1/stations", parsed.path)
        self.assertEqual({"minLat", "maxLat", "minLon", "maxLon"}, set(query))

    def test_parse_shared_location_text_extracts_2gis_coordinates_from_url(self) -> None:
        coordinates = parse_shared_location_text(
            "Улица Гоголя, 7\n"
            "https://2gis.ru/spb/geo/5348660212735615/30.023994,59.852453"
        )

        self.assertEqual(Coordinates(latitude=59.852453, longitude=30.023994), coordinates)

    def test_parse_shared_location_text_ignores_mojibake_around_2gis_url(self) -> None:
        coordinates = parse_shared_location_text(
            "Р”РѕРј-РёРЅС‚РµСЂРЅР°С‚ РґР»СЏ РїСЂРµСЃС‚Р°СЂРµР»С‹С…\n"
            "https://2gis.ru/spb/geo/5348660212735615/30.023994,59.852453"
        )

        self.assertEqual(Coordinates(latitude=59.852453, longitude=30.023994), coordinates)

    def test_parse_shared_location_text_extracts_yandex_ll_coordinates(self) -> None:
        coordinates = parse_shared_location_text(
            "https://yandex.ru/maps/?ll=30.023994%2C59.852453&z=16"
        )

        self.assertEqual(Coordinates(latitude=59.852453, longitude=30.023994), coordinates)

    def test_parse_shared_location_text_extracts_yandex_pt_coordinates(self) -> None:
        coordinates = parse_shared_location_text(
            "https://yandex.ru/maps/?pt=30.023994,59.852453&z=16"
        )

        self.assertEqual(Coordinates(latitude=59.852453, longitude=30.023994), coordinates)

    def test_parse_shared_location_text_returns_none_for_plain_address(self) -> None:
        coordinates = parse_shared_location_text("Санкт-Петербургское ш., 98/1")

        self.assertIsNone(coordinates)


if __name__ == "__main__":
    unittest.main()
