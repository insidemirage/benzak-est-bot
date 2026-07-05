import unittest

from app.stations import (
    Station,
    filter_stations_by_fuel_types,
    format_stations_message,
    format_stations_messages,
    parse_stations_response,
)


class StationsTest(unittest.TestCase):
    def test_formats_available_station_with_yandex_maps_link(self) -> None:
        data = {
            "status": "ok",
            "payload": [
                {
                    "name": "АЗС Север",
                    "addr": "Тестовая область, Тестовый район, улица Примерная, 1",
                    "lat": 10.01,
                    "lon": 20.01,
                    "statusByFuelType": {
                        "92": "available",
                        "95": "available",
                    },
                },
                {
                    "name": "АЗС Юг",
                    "addr": "Тестовая область, Тестовый район, улица Учебная, 2",
                    "lat": 10.02,
                    "lon": 20.02,
                    "statusByFuelType": {
                        "92": "not_available",
                        "95": "maybe_available",
                    },
                },
            ],
        }

        message = format_stations_message(parse_stations_response(data))

        self.assertIn("Автозаправка АЗС Север", message)
        self.assertIn("Есть бензин: 92, 95", message)
        self.assertIn("Автозаправка АЗС Юг", message)
        self.assertIn("Возможно есть: 95", message)
        self.assertIn("https://yandex.ru/maps/?pt=20.01,10.01", message)
        self.assertNotIn("Примерная", message)
        self.assertNotIn("Учебная", message)
        self.assertNotIn("toplivo.tbank.ru/api/v1/stations", message)

    def test_formats_station_with_only_maybe_available_fuel_as_possible(self) -> None:
        data = {
            "status": "ok",
            "payload": [
                {
                    "name": "АЗС Юг",
                    "addr": "Тестовая область, Тестовый район, улица Учебная, 2",
                    "lat": 10.02,
                    "lon": 20.02,
                    "statusByFuelType": {
                        "92": "not_available",
                        "95": "maybe_available",
                    },
                },
            ],
        }

        message = format_stations_message(parse_stations_response(data))

        self.assertIn("Автозаправка АЗС Юг", message)
        self.assertIn("Возможно есть: 95", message)

    def test_ignores_station_when_station_status_is_not_available(self) -> None:
        data = {
            "status": "ok",
            "payload": [
                {
                    "name": "АЗС Юг",
                    "addr": "Тестовая область, Тестовый район, улица Учебная, 2",
                    "lat": 10.02,
                    "lon": 20.02,
                    "status": "not_available",
                    "statusByFuelType": {
                        "92": "available",
                        "95": "available",
                    },
                },
            ],
        }

        message = format_stations_message(parse_stations_response(data))

        self.assertIn("Пока не вижу заправок", message)
        self.assertNotIn("АЗС Юг", message)

    def test_empty_station_list_message_has_no_raw_api_link(self) -> None:
        message = format_stations_message([])

        self.assertIn("Пока не вижу заправок", message)
        self.assertNotIn("toplivo.tbank.ru/api/v1/stations", message)

    def test_formats_station_list_as_chunks_under_message_limit(self) -> None:
        stations = [
            Station(
                id=f"station-{index}",
                name=f"Тестовая АЗС {index}",
                address="Тестовый адрес",
                latitude=10.0 + index / 1000,
                longitude=20.0 + index / 1000,
                yandex_org_id=None,
                available_fuel_types=("92", "95"),
                maybe_available_fuel_types=(),
            )
            for index in range(120)
        ]

        messages = format_stations_messages(stations, max_message_length=1000)

        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 1000 for message in messages))
        self.assertIn("Автозаправка Тестовая АЗС 0", messages[0])
        self.assertIn("Автозаправка Тестовая АЗС 119", messages[-1])

    def test_filters_stations_by_selected_fuel_types(self) -> None:
        station_92 = Station(
            id="station-92",
            name="АЗС 92",
            address="Тестовый адрес",
            latitude=10.0,
            longitude=20.0,
            yandex_org_id=None,
            available_fuel_types=("92",),
            maybe_available_fuel_types=(),
        )
        station_95 = Station(
            id="station-95",
            name="АЗС 95",
            address="Тестовый адрес",
            latitude=10.0,
            longitude=20.0,
            yandex_org_id=None,
            available_fuel_types=("95",),
            maybe_available_fuel_types=(),
        )
        station_100 = Station(
            id="station-100",
            name="АЗС 100",
            address="Тестовый адрес",
            latitude=10.0,
            longitude=20.0,
            yandex_org_id=None,
            available_fuel_types=("100",),
            maybe_available_fuel_types=(),
        )

        filtered = filter_stations_by_fuel_types(
            [station_92, station_95, station_100],
            selected_fuel_types={"95", "100"},
        )

        self.assertEqual([station_95, station_100], filtered)

    def test_filter_keeps_only_selected_fuel_types_in_station_message(self) -> None:
        station = Station(
            id="station-mixed",
            name="АЗС Микс",
            address="Тестовый адрес",
            latitude=10.0,
            longitude=20.0,
            yandex_org_id=None,
            available_fuel_types=("92", "95", "100"),
            maybe_available_fuel_types=(),
        )

        filtered = filter_stations_by_fuel_types([station], selected_fuel_types={"95"})
        message = format_stations_message(filtered)

        self.assertIn("Есть бензин: 95", message)
        self.assertNotIn("92", message)
        self.assertNotIn("100", message)


if __name__ == "__main__":
    unittest.main()
