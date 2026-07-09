import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Optional

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from aiohttp import ClientSession

from app.config import settings
from app.geo import DEFAULT_RADIUS_KM, Coordinates, build_stations_url
from app.location_text import handle_text_location_message
from app.messages import format_checking_message
from app.messages import format_fuel_filter_message as format_fuel_filter_message_text
from app.messages import format_fuel_types_for_text as format_fuel_types_for_text_message
from app.stations import (
    Station,
    filter_stations_by_fuel_types,
    format_stations_messages,
    parse_stations_response,
)
from app.storage import find_cached_stations, get_stats, init_db, record_user, save_check_result
from app.throttle import get_retry_after


router = Router()
CHANGE_LOCATION_TEXT = "Изменить координаты"
CHANGE_FUEL_FILTER_TEXT = "Изменить бензин"
CHANGE_RADIUS_TEXT = "Изменить радиус"
CHECK_STATIONS_TEXT = "Проверить заправки"
ADMIN_STATS_TEXT = "Статистика"
FUEL_FILTER_DONE_TEXT = "Готово"
SHARE_LOCATION_TEXT = "Поделиться местоположением"
CACHE_DISTANCE_KM = 1.0
FUEL_TYPES = ("92", "95", "100")
MAX_RADIUS_KM = 30
RADIUS_OPTIONS_KM = (5, 10, 15, 30)
user_coordinates: dict[int, Coordinates] = {}
user_fuel_types: dict[int, set[str]] = {}
user_radius_km: dict[int, float] = {}
last_check_at: dict[int, float] = {}


def location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SHARE_LOCATION_TEXT, request_location=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_keyboard(user_id: Optional[int] = None) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=CHECK_STATIONS_TEXT)],
        [KeyboardButton(text=CHANGE_FUEL_FILTER_TEXT)],
        [KeyboardButton(text=CHANGE_RADIUS_TEXT)],
        [KeyboardButton(text=CHANGE_LOCATION_TEXT)],
    ]
    if is_admin_user(user_id):
        keyboard.append([KeyboardButton(text=ADMIN_STATS_TEXT)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def radius_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{radius_km} км") for radius_km in RADIUS_OPTIONS_KM[:2]],
            [KeyboardButton(text=f"{radius_km} км") for radius_km in RADIUS_OPTIONS_KM[2:]],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def fuel_filter_keyboard(selected_fuel_types: set[str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=format_fuel_filter_button(fuel_type, selected_fuel_types))
                for fuel_type in FUEL_TYPES
            ],
            [KeyboardButton(text=FUEL_FILTER_DONE_TEXT)],
        ],
        resize_keyboard=True,
    )


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    record_message_user(message)
    await ask_for_radius(message)


@router.message(F.text == CHANGE_LOCATION_TEXT)
async def change_location_handler(message: Message) -> None:
    record_message_user(message)
    await ask_for_location(message)


@router.message(F.text == CHANGE_RADIUS_TEXT)
async def change_radius_handler(message: Message) -> None:
    record_message_user(message)
    await message.answer("Выберите радиус поиска до 30 км:", reply_markup=radius_keyboard())


@router.message(F.text == CHANGE_FUEL_FILTER_TEXT)
async def change_fuel_filter_handler(message: Message) -> None:
    if message.from_user is None:
        return

    record_message_user(message)
    await ask_for_fuel_filter(message)


@router.message(F.text == ADMIN_STATS_TEXT)
async def admin_stats_handler(message: Message) -> None:
    user_id = record_message_user(message)
    if not is_admin_user(user_id):
        return

    stats = get_stats(settings.database_path)
    await message.answer(
        "Статистика бота\n\n"
        f"Пользователей: {stats.users_count}\n"
        f"Запросов всего: {stats.checks_count}",
        reply_markup=main_keyboard(user_id),
    )


@router.message(F.text.in_({f"{radius_km} км" for radius_km in RADIUS_OPTIONS_KM}))
async def radius_handler(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return

    record_message_user(message)
    radius_km = parse_radius(message.text)
    if radius_km is None:
        await message.answer("Выберите радиус кнопкой ниже.", reply_markup=radius_keyboard())
        return

    user_radius_km[message.from_user.id] = radius_km
    if message.from_user.id not in user_fuel_types:
        await message.answer(f"Радиус поиска изменён: {radius_km:g} км.")
        await ask_for_fuel_filter(message)
        return

    if message.from_user.id not in user_coordinates:
        await message.answer(f"Радиус поиска изменён: {radius_km:g} км.")
        await ask_for_location(message)
        return

    await message.answer(
        f"Радиус поиска изменён: {radius_km:g} км.",
        reply_markup=main_keyboard(message.from_user.id),
    )


@router.message(F.text.in_(set(FUEL_TYPES) | {f"{fuel_type} ✓" for fuel_type in FUEL_TYPES}))
async def fuel_filter_toggle_handler(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return

    record_message_user(message)
    fuel_type = parse_fuel_type(message.text)
    if fuel_type is None:
        await ask_for_fuel_filter(message)
        return

    selected_fuel_types = set(user_fuel_types.get(message.from_user.id, set()))
    if fuel_type in selected_fuel_types:
        selected_fuel_types.remove(fuel_type)
    else:
        selected_fuel_types.add(fuel_type)

    user_fuel_types[message.from_user.id] = selected_fuel_types
    await message.answer(
        format_fuel_filter_message(selected_fuel_types),
        reply_markup=fuel_filter_keyboard(selected_fuel_types),
    )


@router.message(F.text == FUEL_FILTER_DONE_TEXT)
async def fuel_filter_done_handler(message: Message) -> None:
    if message.from_user is None:
        return

    record_message_user(message)
    selected_fuel_types = get_required_fuel_types(message.from_user.id)
    if not selected_fuel_types:
        await message.answer("Выберите хотя бы один тип бензина.", reply_markup=fuel_filter_keyboard(set()))
        return

    if message.from_user.id not in user_coordinates:
        await message.answer(f"Фильтр сохранён: {format_fuel_types_for_text(selected_fuel_types)}.")
        await ask_for_location(message)
        return

    await message.answer(
        f"Фильтр сохранён: {format_fuel_types_for_text(selected_fuel_types)}.",
        reply_markup=main_keyboard(message.from_user.id),
    )


@router.message(F.text == CHECK_STATIONS_TEXT)
async def check_stations_handler(message: Message) -> None:
    if message.from_user is None:
        await ask_for_radius(message)
        return

    record_message_user(message)
    radius_km = get_required_radius(message.from_user.id)
    if radius_km is None:
        await ask_for_radius(message)
        return

    selected_fuel_types = get_required_fuel_types(message.from_user.id)
    if not selected_fuel_types:
        await ask_for_fuel_filter(message)
        return

    coordinates = user_coordinates.get(message.from_user.id)
    if coordinates is None:
        await ask_for_location(message)
        return

    now = time.monotonic()
    retry_after = get_retry_after(
        last_check_at,
        message.from_user.id,
        now,
        settings.check_throttle_seconds,
    )
    if retry_after > 0:
        await message.answer(
            f"Проверять заправки можно не чаще одного раза в {settings.check_throttle_seconds} сек. "
            f"Попробуйте ещё раз через {retry_after} сек.",
            reply_markup=main_keyboard(message.from_user.id),
        )
        return

    last_check_at[message.from_user.id] = now
    await check_stations(
        message,
        coordinates,
        radius_km=radius_km,
        selected_fuel_types=selected_fuel_types,
        prefix=f"Проверяю заправки в радиусе {radius_km:g} км...",
    )


@router.message(F.location)
async def location_handler(message: Message) -> None:
    if message.location is None or message.from_user is None:
        await ask_for_radius(message)
        return

    record_message_user(message)
    radius_km = get_required_radius(message.from_user.id)
    if radius_km is None:
        await ask_for_radius(message)
        return

    selected_fuel_types = get_required_fuel_types(message.from_user.id)
    if not selected_fuel_types:
        await ask_for_fuel_filter(message)
        return

    coordinates = Coordinates(
        latitude=message.location.latitude,
        longitude=message.location.longitude,
    )
    user_coordinates[message.from_user.id] = coordinates
    last_check_at[message.from_user.id] = time.monotonic()

    await check_stations(
        message,
        coordinates,
        radius_km=radius_km,
        selected_fuel_types=selected_fuel_types,
        prefix=f"Координаты получил. Проверяю заправки в радиусе {radius_km:g} км...",
    )


@router.message(F.text)
async def shared_location_text_handler(message: Message) -> None:
    if message.from_user is None:
        await ask_for_radius(message)
        return

    record_message_user(message)
    radius_km = get_required_radius(message.from_user.id)
    if radius_km is None:
        await ask_for_radius(message)
        return

    selected_fuel_types = get_required_fuel_types(message.from_user.id)
    if not selected_fuel_types:
        await ask_for_fuel_filter(message)
        return

    await handle_text_location_message(
        message,
        user_id=message.from_user.id,
        radius_km=radius_km,
        selected_fuel_types=selected_fuel_types,
        save_coordinates=save_user_coordinates,
        mark_check_started=mark_check_started,
        check_stations=check_stations,
        location_keyboard=location_keyboard,
    )


async def check_stations(
    message: Message,
    coordinates: Coordinates,
    radius_km: float,
    selected_fuel_types: set[str],
    prefix: str,
) -> None:
    stations_url = build_stations_url(coordinates, radius_km=radius_km)
    loading_message = await message.answer(
        format_checking_message(prefix, stations_url, settings.dev_mode),
        reply_markup=main_keyboard(message.from_user.id if message.from_user else None),
    )
    now = time.time()

    cached_stations = find_cached_stations(
        settings.database_path,
        coordinates=coordinates,
        radius_km=radius_km,
        max_age_seconds=settings.check_throttle_seconds,
        max_distance_km=CACHE_DISTANCE_KM,
        now=now,
    )
    if cached_stations is not None:
        await answer_stations(
            loading_message,
            filter_stations_by_fuel_types(cached_stations, selected_fuel_types),
            user_id=message.from_user.id if message.from_user else None,
        )
        return

    try:
        stations = await fetch_stations(stations_url)
        if message.from_user is not None:
            save_check_result(
                settings.database_path,
                user_id=message.from_user.id,
                coordinates=coordinates,
                radius_km=radius_km,
                stations=stations,
                checked_at=now,
            )
    except Exception:
        logging.exception("Failed to fetch stations")
        await loading_message.answer(
            "Не получилось проверить заправки прямо сейчас. Попробуйте ещё раз немного позже.",
            reply_markup=main_keyboard(message.from_user.id if message.from_user else None),
        )
        return

    await answer_stations(
        loading_message,
        filter_stations_by_fuel_types(stations, selected_fuel_types),
        user_id=message.from_user.id if message.from_user else None,
    )


async def answer_stations(message: Message, stations: list[Station], user_id: Optional[int] = None) -> None:
    station_messages = format_stations_messages(stations)
    for index, station_message in enumerate(station_messages):
        reply_markup = main_keyboard(user_id) if index == len(station_messages) - 1 else None
        await message.answer(station_message, reply_markup=reply_markup)


async def ask_for_location(message: Message) -> None:
    await message.answer(
        "Поделитесь своим местоположением, чтобы я мог проверить заправки рядом с вами.\n\n"
        "Нажмите кнопку ниже и отправьте геолокацию. Если Telegram пишет ошибку, "
        "поделитесь ближайшим к вам местом через Яндекс Навигатор или 2ГИС: "
        "откройте место рядом с вами, нажмите «Поделиться» и отправьте сообщение сюда.\n\n"
        "Потом координаты можно будет изменить.",
        reply_markup=location_keyboard(),
    )


def create_bot() -> Bot:
    session = AiohttpSession(proxy=get_proxy_url())

    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def get_proxy_url() -> Optional[str]:
    return settings.all_proxy or None


def is_admin_user(user_id: Optional[int]) -> bool:
    return settings.admin_id is not None and user_id == settings.admin_id


def record_message_user(message: Message) -> Optional[int]:
    if message.from_user is None:
        return None

    record_user(settings.database_path, message.from_user.id)
    return message.from_user.id


def save_user_coordinates(user_id: int, coordinates: Coordinates) -> None:
    user_coordinates[user_id] = coordinates


def mark_check_started(user_id: int) -> None:
    last_check_at[user_id] = time.monotonic()


async def ask_for_radius(message: Message) -> None:
    await message.answer(
        "Сначала выберите предпочитаемый радиус поиска до 30 км.",
        reply_markup=radius_keyboard(),
    )


def get_required_radius(user_id: int) -> Optional[float]:
    return user_radius_km.get(user_id)


async def ask_for_fuel_filter(message: Message) -> None:
    if message.from_user is None:
        return

    selected_fuel_types = user_fuel_types.get(message.from_user.id, set())
    await message.answer(
        format_fuel_filter_message(selected_fuel_types),
        reply_markup=fuel_filter_keyboard(selected_fuel_types),
    )


def get_required_fuel_types(user_id: int) -> set[str]:
    return set(user_fuel_types.get(user_id, set()))


def parse_fuel_type(text: str) -> Optional[str]:
    fuel_type = text.replace("✓", "").strip()
    if fuel_type not in FUEL_TYPES:
        return None

    return fuel_type


def format_fuel_filter_button(fuel_type: str, selected_fuel_types: set[str]) -> str:
    return f"{fuel_type} ✓" if fuel_type in selected_fuel_types else fuel_type


def format_fuel_types_for_text(fuel_types: set[str]) -> str:
    return format_fuel_types_for_text_message(fuel_types, FUEL_TYPES)


def format_fuel_filter_message(selected_fuel_types: set[str]) -> str:
    return format_fuel_filter_message_text(selected_fuel_types, FUEL_TYPES)


def parse_radius(text: str) -> Optional[float]:
    try:
        radius_km = float(text.replace("км", "").strip().replace(",", "."))
    except ValueError:
        return None

    if radius_km <= 0 or radius_km > MAX_RADIUS_KM:
        return None

    return radius_km


async def fetch_stations(stations_url: str):
    async with ClientSession() as session:
        async with session.get(stations_url) as response:
            response.raise_for_status()
            return parse_stations_response(await response.json())


async def main() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    init_db(settings.database_path)

    bot = create_bot()
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
