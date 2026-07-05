import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.stations import Station
from app.geo import Coordinates
from app.storage import find_cached_stations, init_db, save_check_result, save_stations


class StorageTest(unittest.TestCase):
    def test_save_stations_persists_address_in_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "bot.sqlite3")
            station = Station(
                id="station-1",
                name="АЗС Север",
                address="Тестовая область, Тестовый район, улица Примерная, 1",
                latitude=10.01,
                longitude=20.01,
                yandex_org_id=None,
                available_fuel_types=("92", "95"),
                maybe_available_fuel_types=(),
            )

            init_db(database_path)
            save_stations(database_path, [station])

            with sqlite3.connect(database_path) as connection:
                row = connection.execute(
                    "SELECT address FROM stations WHERE station_id = ?",
                    ("station-1",),
                ).fetchone()

            self.assertEqual(("Тестовая область, Тестовый район, улица Примерная, 1",), row)

    def test_find_cached_stations_returns_recent_nearby_check_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "bot.sqlite3")
            station = Station(
                id="station-1",
                name="АЗС Север",
                address="Тестовая область, Тестовый район, улица Примерная, 1",
                latitude=10.01,
                longitude=20.01,
                yandex_org_id=None,
                available_fuel_types=("92", "95"),
                maybe_available_fuel_types=(),
            )

            save_check_result(
                database_path,
                user_id=1,
                coordinates=Coordinates(latitude=10.0, longitude=20.0),
                radius_km=5,
                stations=[station],
                checked_at=100.0,
            )

            cached_stations = find_cached_stations(
                database_path,
                coordinates=Coordinates(latitude=10.005, longitude=20.0),
                radius_km=5,
                max_age_seconds=30,
                max_distance_km=1,
                now=120.0,
            )

            self.assertEqual([station], cached_stations)

    def test_find_cached_stations_ignores_stale_check_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "bot.sqlite3")
            station = Station(
                id="station-1",
                name="АЗС Север",
                address="Тестовая область, Тестовый район, улица Примерная, 1",
                latitude=10.01,
                longitude=20.01,
                yandex_org_id=None,
                available_fuel_types=("92", "95"),
                maybe_available_fuel_types=(),
            )

            save_check_result(
                database_path,
                user_id=1,
                coordinates=Coordinates(latitude=10.0, longitude=20.0),
                radius_km=5,
                stations=[station],
                checked_at=100.0,
            )

            cached_stations = find_cached_stations(
                database_path,
                coordinates=Coordinates(latitude=10.005, longitude=20.0),
                radius_km=5,
                max_age_seconds=30,
                max_distance_km=1,
                now=131.0,
            )

            self.assertIsNone(cached_stations)

    def test_find_cached_stations_returns_empty_list_for_recent_empty_check_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "bot.sqlite3")

            save_check_result(
                database_path,
                user_id=1,
                coordinates=Coordinates(latitude=10.0, longitude=20.0),
                radius_km=5,
                stations=[],
                checked_at=100.0,
            )

            cached_stations = find_cached_stations(
                database_path,
                coordinates=Coordinates(latitude=10.005, longitude=20.0),
                radius_km=5,
                max_age_seconds=30,
                max_distance_km=1,
                now=120.0,
            )

            self.assertEqual([], cached_stations)

    def test_recent_empty_check_result_overrides_older_positive_nearby_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "bot.sqlite3")
            station = Station(
                id="station-1",
                name="АЗС Юг",
                address="Тестовая область, Тестовый район, улица Учебная, 2",
                latitude=10.02,
                longitude=20.02,
                yandex_org_id=None,
                available_fuel_types=("92", "95"),
                maybe_available_fuel_types=(),
            )

            save_check_result(
                database_path,
                user_id=1,
                coordinates=Coordinates(latitude=10.0, longitude=20.0),
                radius_km=5,
                stations=[station],
                checked_at=100.0,
            )
            save_check_result(
                database_path,
                user_id=2,
                coordinates=Coordinates(latitude=10.0, longitude=20.0),
                radius_km=5,
                stations=[],
                checked_at=110.0,
            )

            cached_stations = find_cached_stations(
                database_path,
                coordinates=Coordinates(latitude=10.005, longitude=20.0),
                radius_km=5,
                max_age_seconds=30,
                max_distance_km=1,
                now=120.0,
            )

            self.assertEqual([], cached_stations)

    def test_find_cached_stations_ignores_smaller_radius_check_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "bot.sqlite3")
            station = Station(
                id="station-1",
                name="АЗС Север",
                address="Тестовая область, Тестовый район, улица Примерная, 1",
                latitude=10.01,
                longitude=20.01,
                yandex_org_id=None,
                available_fuel_types=("92", "95"),
                maybe_available_fuel_types=(),
            )

            save_check_result(
                database_path,
                user_id=1,
                coordinates=Coordinates(latitude=10.0, longitude=20.0),
                radius_km=5,
                stations=[station],
                checked_at=100.0,
            )

            cached_stations = find_cached_stations(
                database_path,
                coordinates=Coordinates(latitude=10.005, longitude=20.0),
                radius_km=30,
                max_age_seconds=30,
                max_distance_km=1,
                now=120.0,
            )

            self.assertIsNone(cached_stations)

    def test_find_cached_stations_uses_larger_radius_check_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database_path = str(Path(tmpdir) / "bot.sqlite3")
            station = Station(
                id="station-1",
                name="АЗС Север",
                address="Тестовая область, Тестовый район, улица Примерная, 1",
                latitude=10.01,
                longitude=20.01,
                yandex_org_id=None,
                available_fuel_types=("92", "95"),
                maybe_available_fuel_types=(),
            )

            save_check_result(
                database_path,
                user_id=1,
                coordinates=Coordinates(latitude=10.0, longitude=20.0),
                radius_km=30,
                stations=[station],
                checked_at=100.0,
            )

            cached_stations = find_cached_stations(
                database_path,
                coordinates=Coordinates(latitude=10.005, longitude=20.0),
                radius_km=5,
                max_age_seconds=30,
                max_distance_km=1,
                now=120.0,
            )

            self.assertEqual([station], cached_stations)


if __name__ == "__main__":
    unittest.main()
