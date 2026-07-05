import unittest

from app.messages import format_checking_message


class MessagesTest(unittest.TestCase):
    def test_format_checking_message_hides_toplivo_url_outside_dev_mode(self) -> None:
        message = format_checking_message("Проверяю заправки...", "https://toplivo.example/api", False)

        self.assertEqual("Проверяю заправки...", message)

    def test_format_checking_message_includes_toplivo_url_in_dev_mode(self) -> None:
        message = format_checking_message("Проверяю заправки...", "https://toplivo.example/api", True)

        self.assertIn("Проверяю заправки...", message)
        self.assertIn("https://toplivo.example/api", message)


if __name__ == "__main__":
    unittest.main()

