"""Save TUI screenshots for the docs with a fake console: python scripts/screenshots.py"""
import asyncio
import pathlib
from unittest import mock

from chilichip import platform_api
from chilichip.console import InstalledGame, LoaderVersion
from chilichip.tui import ChilichipApp

OUT = pathlib.Path(__file__).parent.parent / 'docs' / 'assets' / 'screenshots'
GAMES = [
    InstalledGame(4, 145869, 'ChiliChip OS', 'chilichip', 'v1.0.0', 1),
    InstalledGame(7, 402000, 'Bitsy', 'TeriyakiGod', 'v0.2.0', 2),
    InstalledGame(14, 51006, 'Doom Fire', 'andreban', 'v1.0.0', 3),
    InstalledGame(15, 98304, 'Chili Snake', 'chilichip', 'v1.2.0', 4),
]

LIBRARY = [  # the shape of GET /api/device/library/ on chili-platform
    {'id': 12, 'title': 'Cat Adventure', 'author': 'ada', 'engine': 'bitsy', 'size': 18342,
     'sha256': '', 'updated_at': '2026-11-10T09:00:00Z', 'download_url': '/api/device/games/12.bitsy'},
    {'id': 15, 'title': 'Drum Night', 'author': 'kacper', 'engine': 'beat', 'size': 6120,
     'sha256': '', 'updated_at': '2026-11-09T09:00:00Z', 'download_url': '/api/device/games/15.beat'},
    {'id': 21, 'title': 'Lighthouse Keeper', 'author': 'pawel', 'engine': 'bitsy', 'size': 40960,
     'sha256': '', 'updated_at': '2026-11-08T09:00:00Z', 'download_url': '/api/device/games/21.bitsy'},
]


class FakeConsole:
    def __init__(self, port):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def version(self):
        return LoaderVersion('v1.0.1', (0, 6))

    def games(self):
        return GAMES


async def main():
    with mock.patch('chilichip.tui.find_console', return_value='/dev/ttyACM0'), \
            mock.patch('chilichip.tui.Console', FakeConsole), \
            mock.patch.object(platform_api, 'load_token', return_value='token'), \
            mock.patch.object(platform_api.Platform, 'library', return_value=LIBRARY):
        app = ChilichipApp()
        async with app.run_test(size=(100, 34)) as pilot:
            await app.workers.wait_for_complete()
            await pilot.pause(0.3)
            app.write('Installed chili-snake.blit')
            app.save_screenshot('tui-console.svg', str(OUT))
            for tab in ('library', 'update', 'new', 'build'):
                app.query_one('TabbedContent').active = tab
                await pilot.pause(0.3)
                app.save_screenshot(f'tui-{tab}.svg', str(OUT))


asyncio.run(main())

for svg in OUT.glob('tui-*.svg'):  # the repo's make check refuses trailing whitespace
    svg.write_text(''.join(line.rstrip() + '\n' for line in svg.read_text().splitlines()))
