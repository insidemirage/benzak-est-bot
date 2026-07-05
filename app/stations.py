from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Optional


AVAILABLE_STATUS = "available"
MAYBE_AVAILABLE_STATUS = "maybe_available"
NOT_AVAILABLE_STATUS = "not_available"
TELEGRAM_MESSAGE_LIMIT = 4096


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    address: str
    latitude: float
    longitude: float
    yandex_org_id: Optional[str]
    available_fuel_types: tuple[str, ...]
    maybe_available_fuel_types: tuple[str, ...]


def parse_stations_response(data: dict[str, Any]) -> list[Station]:
    payload = data.get("payload")
    if not isinstance(payload, list):
        return []

    stations: list[Station] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        status_by_fuel_type = item.get("statusByFuelType")
        if not isinstance(status_by_fuel_type, dict):
            status_by_fuel_type = {}

        if item.get("status") == NOT_AVAILABLE_STATUS:
            continue

        available = sorted(
            fuel_type
            for fuel_type, status in status_by_fuel_type.items()
            if status == AVAILABLE_STATUS
        )
        maybe_available = sorted(
            fuel_type
            for fuel_type, status in status_by_fuel_type.items()
            if status == MAYBE_AVAILABLE_STATUS
        )

        if not available and not maybe_available:
            continue

        stations.append(
            Station(
                id=str(item.get("id") or item.get("yandexOrgId") or f"{item.get('lat')},{item.get('lon')}"),
                name=str(item.get("name") or "Автозаправка"),
                address=str(item.get("addr") or ""),
                latitude=float(item.get("lat") or 0),
                longitude=float(item.get("lon") or 0),
                yandex_org_id=str(item["yandexOrgId"]) if item.get("yandexOrgId") else None,
                available_fuel_types=tuple(available),
                maybe_available_fuel_types=tuple(maybe_available),
            )
        )

    return stations


def format_stations_message(stations: list[Station]) -> str:
    return "\n\n".join(format_stations_messages(stations))


def format_stations_messages(
    stations: list[Station],
    max_message_length: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    if not stations:
        return [
            "Пока не вижу заправок с доступным бензином рядом.\n\n"
            "Я продолжу проверять этот район, а координаты можно изменить кнопкой ниже."
        ]

    messages: list[str] = []
    current_message = "Нашёл заправки рядом:"
    for station in stations:
        station_block = format_station(station)
        candidate = f"{current_message}\n\n{station_block}"

        if len(candidate) <= max_message_length:
            current_message = candidate
            continue

        messages.append(current_message)
        current_message = station_block

    messages.append(current_message)

    return messages


def format_station(station: Station) -> str:
    lines = [f"<b>Автозаправка {html.escape(station.name)}</b>"]

    if station.available_fuel_types:
        lines.append(f"Есть бензин: {format_fuel_types(station.available_fuel_types)}")

    if station.maybe_available_fuel_types:
        lines.append(f"Возможно есть: {format_fuel_types(station.maybe_available_fuel_types)}")

    maps_url = build_yandex_maps_url(station)
    lines.append(f'<a href="{html.escape(maps_url, quote=True)}">Открыть в Яндекс.Картах</a>')

    return "\n".join(lines)


def format_fuel_types(fuel_types: tuple[str, ...]) -> str:
    return ", ".join(html.escape(fuel_type) for fuel_type in fuel_types)


def build_yandex_maps_url(station: Station) -> str:
    if station.yandex_org_id:
        return f"https://yandex.ru/maps/org/{station.yandex_org_id}"

    return f"https://yandex.ru/maps/?pt={station.longitude},{station.latitude}&z=16"
