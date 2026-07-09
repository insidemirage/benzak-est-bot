import unittest

from app.geo import Coordinates
from app.location_text import (
    LOCATION_PARSE_ERROR_TEXT,
    LOCATION_REQUEST_TEXT,
    NAVIGATOR_HELP_BUTTON_TEXT,
    NAVIGATOR_HELP_TEXT,
    SHARE_TELEGRAM_LOCATION_TEXT,
    handle_text_location_message,
)


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.answers = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class LocationTextTest(unittest.IsolatedAsyncioTestCase):
    def test_location_request_text_shows_two_clear_location_options(self) -> None:
        self.assertIn("1. Через Telegram", LOCATION_REQUEST_TEXT)
        self.assertIn("2. Через Яндекс Навигатор или 2ГИС", LOCATION_REQUEST_TEXT)
        self.assertIn(SHARE_TELEGRAM_LOCATION_TEXT, LOCATION_REQUEST_TEXT)
        self.assertIn(NAVIGATOR_HELP_BUTTON_TEXT, LOCATION_REQUEST_TEXT)

    def test_navigator_help_text_explains_share_flow(self) -> None:
        self.assertIn("Яндекс Навигатор или 2ГИС", NAVIGATOR_HELP_TEXT)
        self.assertIn("выберите ближайшее к вам место", NAVIGATOR_HELP_TEXT.lower())
        self.assertIn("Поделиться", NAVIGATOR_HELP_TEXT)
        self.assertIn("этот чат", NAVIGATOR_HELP_TEXT)

    async def test_handle_text_location_message_saves_coordinates_and_checks_stations(self) -> None:
        message = FakeMessage("https://2gis.ru/spb/geo/5348660212735615/30.023994,59.852453")
        saved = {}
        marked = []
        checks = []

        async def resolve_coordinates(text: str):
            return Coordinates(latitude=59.852453, longitude=30.023994)

        async def check_stations(message, coordinates, radius_km, selected_fuel_types, prefix):
            checks.append((message, coordinates, radius_km, selected_fuel_types, prefix))

        handled = await handle_text_location_message(
            message,
            user_id=123,
            radius_km=10,
            selected_fuel_types={"95"},
            save_coordinates=lambda user_id, coordinates: saved.update({user_id: coordinates}),
            mark_check_started=lambda user_id: marked.append(user_id),
            check_stations=check_stations,
            location_keyboard=lambda: "location-keyboard",
            resolve_coordinates=resolve_coordinates,
        )

        self.assertTrue(handled)
        self.assertEqual({123: Coordinates(latitude=59.852453, longitude=30.023994)}, saved)
        self.assertEqual([123], marked)
        self.assertEqual(
            [
                (
                    message,
                    Coordinates(latitude=59.852453, longitude=30.023994),
                    10,
                    {"95"},
                    "Место получил. Проверяю заправки в радиусе 10 км...",
                )
            ],
            checks,
        )
        self.assertEqual([], message.answers)

    async def test_handle_text_location_message_answers_with_hint_when_location_not_found(self) -> None:
        message = FakeMessage("Санкт-Петербургское ш., 98/1")
        saved = {}
        marked = []
        checks = []

        async def resolve_coordinates(text: str):
            return None

        async def check_stations(message, coordinates, radius_km, selected_fuel_types, prefix):
            checks.append((message, coordinates, radius_km, selected_fuel_types, prefix))

        handled = await handle_text_location_message(
            message,
            user_id=123,
            radius_km=10,
            selected_fuel_types={"95"},
            save_coordinates=lambda user_id, coordinates: saved.update({user_id: coordinates}),
            mark_check_started=lambda user_id: marked.append(user_id),
            check_stations=check_stations,
            location_keyboard=lambda: "location-keyboard",
            resolve_coordinates=resolve_coordinates,
        )

        self.assertFalse(handled)
        self.assertEqual({}, saved)
        self.assertEqual([], marked)
        self.assertEqual([], checks)
        self.assertEqual([(LOCATION_PARSE_ERROR_TEXT, "location-keyboard")], message.answers)


if __name__ == "__main__":
    unittest.main()
