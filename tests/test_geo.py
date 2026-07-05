import unittest
from urllib.parse import parse_qs, urlparse

from app.geo import Coordinates, build_bounding_box, build_stations_url


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


if __name__ == "__main__":
    unittest.main()
