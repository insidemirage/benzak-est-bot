import logging
from dataclasses import dataclass
from typing import Any


SEND_UPDATE_TEXT = "Отправить обновление"
CONFIRM_SEND_UPDATE_TEXT = "Подтвердить отправку обновления"
CANCEL_SEND_UPDATE_TEXT = "Отмена"
UPDATE_ANNOUNCEMENT_TEXT = (
    "<b>Обновление Benzak Bot</b>\n\n"
    "Теперь место для поиска можно отправить не только через геолокацию Telegram.\n\n"
    "Если Telegram пишет «Произошла ошибка. Пожалуйста, попробуйте позже», "
    "поделитесь ближайшим к вам местом через Яндекс Навигатор или 2ГИС:\n"
    "1. Откройте Яндекс Навигатор или 2ГИС.\n"
    "2. Выберите ближайшее к вам место на карте.\n"
    "3. Нажмите «Поделиться».\n"
    "4. Отправьте сообщение с местом в этот чат.\n\n"
    "Я приму ссылку как геолокацию и проверю заправки рядом."
)


@dataclass(frozen=True)
class UpdateBroadcastResult:
    sent_count: int
    failed_count: int


def format_update_preview(users_count: int) -> str:
    return (
        "Предпросмотр рассылки обновления\n\n"
        f"Пользователей: {users_count}\n\n"
        f"{UPDATE_ANNOUNCEMENT_TEXT}\n\n"
        "Если всё верно, подтвердите отправку."
    )


def format_update_result(result: UpdateBroadcastResult) -> str:
    return (
        "Рассылка обновления завершена.\n\n"
        f"Успешно: {result.sent_count}\n"
        f"Ошибок: {result.failed_count}"
    )


async def send_update_to_users(
    bot: Any,
    user_ids: list[int],
    message_text: str = UPDATE_ANNOUNCEMENT_TEXT,
) -> UpdateBroadcastResult:
    sent_count = 0
    failed_count = 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, message_text)
        except Exception:
            logging.exception("Failed to send update announcement to user %s", user_id)
            failed_count += 1
            continue

        sent_count += 1

    return UpdateBroadcastResult(sent_count=sent_count, failed_count=failed_count)
