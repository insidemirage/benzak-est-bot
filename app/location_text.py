from typing import Any, Awaitable, Callable, Optional

from app.geo import Coordinates
from app.shared_locations import resolve_shared_location_text


SHARE_TELEGRAM_LOCATION_TEXT = "Отправить геолокацию Telegram"
NAVIGATOR_HELP_BUTTON_TEXT = "Как поделиться из навигатора"
LOCATION_REQUEST_TEXT = (
    "Поделитесь местом, чтобы я мог проверить заправки рядом с вами.\n\n"
    f"1. Через Telegram: нажмите «{SHARE_TELEGRAM_LOCATION_TEXT}».\n\n"
    "2. Через Яндекс Навигатор или 2ГИС: нажмите "
    f"«{NAVIGATOR_HELP_BUTTON_TEXT}», если Telegram пишет ошибку."
)
NAVIGATOR_HELP_TEXT = (
    "Как поделиться через Яндекс Навигатор или 2ГИС:\n\n"
    "1. Откройте Яндекс Навигатор или 2ГИС.\n"
    "2. Выберите ближайшее к вам место на карте.\n"
    "3. Нажмите «Поделиться».\n"
    "4. Выберите Telegram и отправьте сообщение в этот чат.\n\n"
    "Я приму ссылку как геолокацию и проверю заправки рядом."
)
LOCATION_PARSE_ERROR_TEXT = (
    "Не смог определить место. Поделитесь ближайшим к вам местом через "
    "Яндекс Навигатор или 2ГИС, либо отправьте геолокацию кнопкой ниже."
)


ResolveCoordinates = Callable[[str], Awaitable[Optional[Coordinates]]]
SaveCoordinates = Callable[[int, Coordinates], None]
MarkCheckStarted = Callable[[int], None]
CheckStations = Callable[[Any, Coordinates, float, set[str], str], Awaitable[None]]
LocationKeyboard = Callable[[], Any]


async def handle_text_location_message(
    message: Any,
    *,
    user_id: int,
    radius_km: float,
    selected_fuel_types: set[str],
    save_coordinates: SaveCoordinates,
    mark_check_started: MarkCheckStarted,
    check_stations: CheckStations,
    location_keyboard: LocationKeyboard,
    resolve_coordinates: ResolveCoordinates = resolve_shared_location_text,
) -> bool:
    coordinates = await resolve_coordinates(message.text or "")
    if coordinates is None:
        await message.answer(LOCATION_PARSE_ERROR_TEXT, reply_markup=location_keyboard())
        return False

    save_coordinates(user_id, coordinates)
    mark_check_started(user_id)
    await check_stations(
        message,
        coordinates,
        radius_km,
        selected_fuel_types,
        f"Место получил. Проверяю заправки в радиусе {radius_km:g} км...",
    )
    return True
