from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from app.geo import Coordinates
from app.stations import Station


def init_db(database_path: str) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stations (
                station_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                yandex_org_id TEXT,
                available_fuel_types TEXT NOT NULL,
                maybe_available_fuel_types TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS station_checks (
                check_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                radius_km REAL NOT NULL DEFAULT 5,
                checked_at REAL NOT NULL
            )
            """
        )
        ensure_column(connection, "station_checks", "radius_km", "REAL NOT NULL DEFAULT 5")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS station_check_results (
                check_id INTEGER NOT NULL,
                station_id TEXT NOT NULL,
                PRIMARY KEY (check_id, station_id),
                FOREIGN KEY (check_id) REFERENCES station_checks(check_id),
                FOREIGN KEY (station_id) REFERENCES stations(station_id)
            )
            """
        )


def save_stations(database_path: str, stations: list[Station]) -> None:
    if not stations:
        return

    init_db(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO stations (
                station_id,
                name,
                address,
                latitude,
                longitude,
                yandex_org_id,
                available_fuel_types,
                maybe_available_fuel_types,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(station_id) DO UPDATE SET
                name = excluded.name,
                address = excluded.address,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                yandex_org_id = excluded.yandex_org_id,
                available_fuel_types = excluded.available_fuel_types,
                maybe_available_fuel_types = excluded.maybe_available_fuel_types,
                updated_at = CURRENT_TIMESTAMP
            """,
            [
                (
                    station.id,
                    station.name,
                    station.address,
                    station.latitude,
                    station.longitude,
                    station.yandex_org_id,
                    json.dumps(station.available_fuel_types, ensure_ascii=False),
                    json.dumps(station.maybe_available_fuel_types, ensure_ascii=False),
                )
                for station in stations
            ],
        )


def save_check_result(
    database_path: str,
    user_id: int,
    coordinates: Coordinates,
    radius_km: float,
    stations: list[Station],
    checked_at: float,
) -> None:
    init_db(database_path)
    save_stations(database_path, stations)

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO station_checks (user_id, latitude, longitude, radius_km, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, coordinates.latitude, coordinates.longitude, radius_km, checked_at),
        )
        check_id = cursor.lastrowid
        connection.executemany(
            """
            INSERT INTO station_check_results (check_id, station_id)
            VALUES (?, ?)
            """,
            [(check_id, station.id) for station in stations],
        )


def find_cached_stations(
    database_path: str,
    coordinates: Coordinates,
    radius_km: float,
    max_age_seconds: int,
    max_distance_km: float,
    now: float,
) -> list[Station] | None:
    init_db(database_path)
    min_checked_at = now - max_age_seconds

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        check_rows = connection.execute(
            """
            SELECT check_id, latitude, longitude, radius_km
            FROM station_checks
            WHERE checked_at >= ? AND radius_km >= ?
            ORDER BY checked_at DESC
            """,
            (min_checked_at, radius_km),
        ).fetchall()

        for check_row in check_rows:
            check_coordinates = Coordinates(
                latitude=check_row["latitude"],
                longitude=check_row["longitude"],
            )
            if distance_km(coordinates, check_coordinates) > max_distance_km:
                continue

            station_rows = connection.execute(
                """
                SELECT
                    s.station_id,
                    s.name,
                    s.address,
                    s.latitude,
                    s.longitude,
                    s.yandex_org_id,
                    s.available_fuel_types,
                    s.maybe_available_fuel_types
                FROM station_check_results scr
                JOIN stations s ON s.station_id = scr.station_id
                WHERE scr.check_id = ?
                ORDER BY s.name
                """,
                (check_row["check_id"],),
            ).fetchall()

            return [station_from_row(row) for row in station_rows]

    return None


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if any(column[1] == column_name for column in columns):
        return

    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def station_from_row(row: sqlite3.Row) -> Station:
    return Station(
        id=row["station_id"],
        name=row["name"],
        address=row["address"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        yandex_org_id=row["yandex_org_id"],
        available_fuel_types=tuple(json.loads(row["available_fuel_types"])),
        maybe_available_fuel_types=tuple(json.loads(row["maybe_available_fuel_types"])),
    )


def distance_km(left: Coordinates, right: Coordinates) -> float:
    lat_delta = math.radians(right.latitude - left.latitude)
    lon_delta = math.radians(right.longitude - left.longitude)
    left_lat = math.radians(left.latitude)
    right_lat = math.radians(right.latitude)

    haversine = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(left_lat) * math.cos(right_lat) * math.sin(lon_delta / 2) ** 2
    )

    return 6371.0 * 2 * math.asin(math.sqrt(haversine))
