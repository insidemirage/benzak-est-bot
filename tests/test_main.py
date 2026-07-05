import unittest

from app.throttle import get_retry_after


class MainTest(unittest.TestCase):
    def test_retry_after_blocks_checks_more_often_than_once_per_minute(self) -> None:
        last_check_at = {123: 100.0}

        retry_after = get_retry_after(last_check_at, 123, 120.0, throttle_seconds=60)

        self.assertEqual(41, retry_after)

    def test_retry_after_allows_check_after_minute(self) -> None:
        last_check_at = {123: 100.0}

        retry_after = get_retry_after(last_check_at, 123, 160.0, throttle_seconds=60)

        self.assertEqual(0, retry_after)

    def test_retry_after_uses_configurable_delay(self) -> None:
        last_check_at = {123: 100.0}

        retry_after = get_retry_after(last_check_at, 123, 120.0, throttle_seconds=30)

        self.assertEqual(11, retry_after)

if __name__ == "__main__":
    unittest.main()
