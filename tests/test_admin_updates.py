import unittest

from app.admin_updates import (
    UPDATE_ANNOUNCEMENT_TEXT,
    UpdateBroadcastResult,
    format_update_preview,
    format_update_result,
    send_update_to_users,
)


class FakeBot:
    def __init__(self, failing_user_ids=None) -> None:
        self.failing_user_ids = set(failing_user_ids or [])
        self.messages = []

    async def send_message(self, user_id: int, text: str) -> None:
        if user_id in self.failing_user_ids:
            raise RuntimeError("send failed")

        self.messages.append((user_id, text))


class AdminUpdatesTest(unittest.IsolatedAsyncioTestCase):
    def test_update_announcement_describes_navigator_and_2gis_flow(self) -> None:
        self.assertIn("обновление", UPDATE_ANNOUNCEMENT_TEXT.lower())
        self.assertIn("Яндекс Навигатор", UPDATE_ANNOUNCEMENT_TEXT)
        self.assertIn("2ГИС", UPDATE_ANNOUNCEMENT_TEXT)
        self.assertIn("Поделиться", UPDATE_ANNOUNCEMENT_TEXT)

    def test_format_update_preview_includes_user_count_and_confirmation_hint(self) -> None:
        preview = format_update_preview(users_count=3)

        self.assertIn("Пользователей: 3", preview)
        self.assertIn(UPDATE_ANNOUNCEMENT_TEXT, preview)
        self.assertIn("подтвердите отправку", preview.lower())

    async def test_send_update_to_users_counts_successes_and_failures(self) -> None:
        bot = FakeBot(failing_user_ids={2})

        with self.assertLogs(level="ERROR"):
            result = await send_update_to_users(bot, [1, 2, 3])

        self.assertEqual(UpdateBroadcastResult(sent_count=2, failed_count=1), result)
        self.assertEqual(
            [
                (1, UPDATE_ANNOUNCEMENT_TEXT),
                (3, UPDATE_ANNOUNCEMENT_TEXT),
            ],
            bot.messages,
        )

    def test_format_update_result_reports_counts(self) -> None:
        message = format_update_result(UpdateBroadcastResult(sent_count=2, failed_count=1))

        self.assertIn("Успешно: 2", message)
        self.assertIn("Ошибок: 1", message)


if __name__ == "__main__":
    unittest.main()
