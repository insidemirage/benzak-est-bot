import unittest

from app.geo import Coordinates
from app.shared_locations import ResolvedPage, resolve_shared_location_text


class SharedLocationsTest(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_shared_location_text_uses_direct_link_without_fetching(self) -> None:
        async def fetch_page(url: str) -> ResolvedPage:
            raise AssertionError(f"unexpected fetch for {url}")

        coordinates = await resolve_shared_location_text(
            "https://2gis.ru/spb/geo/5348660212735615/30.023994,59.852453",
            fetch_page=fetch_page,
        )

        self.assertEqual(Coordinates(latitude=59.852453, longitude=30.023994), coordinates)

    async def test_resolve_shared_location_text_uses_yandex_redirect_url(self) -> None:
        async def fetch_page(url: str) -> ResolvedPage:
            return ResolvedPage(
                final_url="https://yandex.ru/maps/?ll=30.023994%2C59.852453&z=16",
                text="",
            )

        coordinates = await resolve_shared_location_text(
            "https://yandex.ru/navi/org/dom_internat_dlya_prestarelykh_i_invalidov/1156361900",
            fetch_page=fetch_page,
        )

        self.assertEqual(Coordinates(latitude=59.852453, longitude=30.023994), coordinates)

    async def test_resolve_shared_location_text_uses_yandex_page_coordinates(self) -> None:
        async def fetch_page(url: str) -> ResolvedPage:
            return ResolvedPage(
                final_url=url,
                text='{"coordinates":[30.023994,59.852453]}',
            )

        coordinates = await resolve_shared_location_text(
            "https://yandex.ru/navi/org/dom_internat_dlya_prestarelykh_i_invalidov/1156361900",
            fetch_page=fetch_page,
        )

        self.assertEqual(Coordinates(latitude=59.852453, longitude=30.023994), coordinates)


if __name__ == "__main__":
    unittest.main()
