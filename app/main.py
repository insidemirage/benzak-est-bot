import asyncio
import logging
import sys
import time
from pathlib import Path

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
from app.messages import format_checking_message
from app.stations import Station, format_stations_messages, parse_stations_response
from app.storage import find_cached_stations, init_db, save_check_result
from app.throttle import get_retry_after


router = Router()
CHANGE_LOCATION_TEXT = "Изменить координаты"
CHANGE_RADIUS_TEXT = "Изменить радиус"
CHECK_STATIONS_TEXT = "Проверить заправки"
SHARE_LOCATION_TEXT = "Поделиться местоположением"
CACHE_DISTANCE_KM = 1.0
MAX_RADIUS_KM = 30
RADIUS_OPTIONS_KM = (5, 10, 15, 30)
user_coordinates: dict[int, Coordinates] = {}
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


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CHECK_STATIONS_TEXT)],
            [KeyboardButton(text=CHANGE_RADIUS_TEXT)],
            [KeyboardButton(text=CHANGE_LOCATION_TEXT)],
        ],
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


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await ask_for_radius(message)


@router.message(F.text == CHANGE_LOCATION_TEXT)
async def change_location_handler(message: Message) -> None:
    await ask_for_location(message)


@router.message(F.text == CHANGE_RADIUS_TEXT)
async def change_radius_handler(message: Message) -> None:
    await message.answer("Выберите радиус поиска до 30 км:", reply_markup=radius_keyboard())


@router.message(F.text.in_({f"{radius_km} км" for radius_km in RADIUS_OPTIONS_KM}))
async def radius_handler(message: Message) -> None:
    if message.from_user is None or message.text is None:
        return

    radius_km = parse_radius(message.text)
    if radius_km is None:
        await message.answer("Выберите радиус кнопкой ниже.", reply_markup=radius_keyboard())
        return

    user_radius_km[message.from_user.id] = radius_km
    if message.from_user.id not in user_coordinates:
        await message.answer(f"Радиус поиска изменён: {radius_km:g} км.")
        await ask_for_location(message)
        return

    await message.answer(f"Радиус поиска изменён: {radius_km:g} км.", reply_markup=main_keyboard())


@router.message(F.text == CHECK_STATIONS_TEXT)
async def check_stations_handler(message: Message) -> None:
    if message.from_user is None:
        await ask_for_radius(message)
        return

    radius_km = get_required_radius(message.from_user.id)
    if radius_km is None:
        await ask_for_radius(message)
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
            reply_markup=main_keyboard(),
        )
        return

    last_check_at[message.from_user.id] = now
    await check_stations(
        message,
        coordinates,
        radius_km=radius_km,
        prefix=f"Проверяю заправки в радиусе {radius_km:g} км...",
    )


@router.message(F.location)
async def location_handler(message: Message) -> None:
    if message.location is None or message.from_user is None:
        await ask_for_radius(message)
        return

    radius_km = get_required_radius(message.from_user.id)
    if radius_km is None:
        await ask_for_radius(message)
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
        prefix=f"Координаты получил. Проверяю заправки в радиусе {radius_km:g} км...",
    )


async def check_stations(
    message: Message,
    coordinates: Coordinates,
    radius_km: float,
    prefix: str,
) -> None:
    stations_url = build_stations_url(coordinates, radius_km=radius_km)
    loading_message = await message.answer(
        format_checking_message(prefix, stations_url, settings.dev_mode),
        reply_markup=main_keyboard(),
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
        await answer_stations(loading_message, cached_stations)
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
            reply_markup=main_keyboard(),
        )
        return

    await answer_stations(loading_message, stations)


async def answer_stations(message: Message, stations: list[Station]) -> None:
    station_messages = format_stations_messages(stations)
    for index, station_message in enumerate(station_messages):
        reply_markup = main_keyboard() if index == len(station_messages) - 1 else None
        await message.answer(station_message, reply_markup=reply_markup)


async def ask_for_location(message: Message) -> None:
    await message.answer(
        "Поделитесь своим местоположением, чтобы я мог проверить заправки рядом с вами.\n\n"
        "Нажмите кнопку ниже и отправьте геолокацию. Потом координаты можно будет изменить.",
        reply_markup=location_keyboard(),
    )


def create_bot() -> Bot:
    session = AiohttpSession(proxy=get_proxy_url())

    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def get_proxy_url() -> str | None:
    return settings.all_proxy or None


async def ask_for_radius(message: Message) -> None:
    await message.answer(
        "Сначала выберите предпочитаемый радиус поиска до 30 км.",
        reply_markup=radius_keyboard(),
    )


def get_required_radius(user_id: int) -> float | None:
    return user_radius_km.get(user_id)


def parse_radius(text: str) -> float | None:
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
