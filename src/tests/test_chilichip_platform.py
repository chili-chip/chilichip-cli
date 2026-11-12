"""chilichip login, library and install --from-platform against a fake chili-platform over HTTP."""
import hashlib
import json
import os
import stat

import mock
import pytest
from click.testing import CliRunner
from fakes import FakeConsole, FakePlatform

from chilichip import ChilichipError, cli
from chilichip import platform_api as chili

BITSY = b'Cat Adventure\n\n# BITSY VERSION 8.12\n'
BEAT = b'{"beat": 1}'


def invoke(*args, **kwargs):
    return CliRunner().invoke(cli.main, args, **kwargs)


def library_games():
    return [
        {'id': 12, 'title': 'Cat Adventure', 'data': BITSY},
        {'id': 15, 'title': 'Drum Night', 'data': BEAT, 'engine': 'beat', 'extension': '.beat'},
    ]


def login(platform):
    result = invoke('login', '--platform', platform.url, '--name', 'Test PC')
    assert result.exit_code == 0, result.output
    return result


# login: RFC 8628 device authorization grant


def test_login_shows_the_code_and_saves_the_token(config):
    with FakePlatform() as platform:
        result = login(platform)

        assert 'BCDF-GHJK' in result.output
        assert 'https://platform.example/link' in result.output
        assert 'Linked as "Test PC"' in result.output

        method, path, _, body = platform.requests[0]
        assert (method, path, body) == ('POST', '/api/devices/authorize/', {'name': 'Test PC'})
        polls = [r for r in platform.requests if r[1] == '/api/devices/token/']
        assert len(polls) == 2  # one authorization_pending, then the token
        assert polls[0][3] == {'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                               'device_code': 'secret-device-code'}

        saved = config / 'config' / 'platform.json'
        assert json.loads(saved.read_text())[platform.url]['token'] == 'device-token-123'
        if os.name == 'posix':
            assert stat.S_IMODE(saved.stat().st_mode) == 0o600


def test_login_waits_longer_after_slow_down(monkeypatch):
    sleeps = []
    monkeypatch.setattr(chili.time, 'sleep', sleeps.append)
    with FakePlatform(outcome='slow_down', polls_before_approval=2) as platform:
        login(platform)
    # RFC 8628 3.5: on slow_down the interval grows by 5 seconds and stays that way
    assert sleeps == [5, 10, 15]


@pytest.mark.parametrize('outcome, message', [
    ('deny', 'was denied'),
    ('expire', 'code expired'),
])
def test_login_denied_or_expired(outcome, message, config):
    with FakePlatform(outcome=outcome) as platform:
        result = invoke('login', '--platform', platform.url)
    assert result.exit_code == 1
    assert message in result.output
    assert not (config / 'config' / 'platform.json').exists()


def test_login_gives_up_when_the_code_runs_out(monkeypatch):
    clock = iter(range(0, 10_000, 300))
    monkeypatch.setattr(chili.time, 'monotonic', lambda: next(clock))
    with FakePlatform(polls_before_approval=100) as platform:
        result = invoke('login', '--platform', platform.url)
    assert result.exit_code == 1
    assert 'code expired' in result.output


def test_platform_unreachable():
    result = invoke('login', '--platform', 'http://127.0.0.1:9')
    assert result.exit_code == 1
    assert 'Cannot reach' in result.output
    assert 'Traceback' not in result.output


def test_logout_forgets_the_token(config):
    with FakePlatform() as platform:
        login(platform)
        result = invoke('logout', '--platform', platform.url)
        assert result.exit_code == 0, result.output
        assert 'Settings' in result.output  # where to revoke the device for good
        result = invoke('library', '--platform', platform.url)
    assert result.exit_code == 1
    assert 'chilichip login' in result.output


def test_platform_url_from_the_environment(monkeypatch):
    with FakePlatform(games=library_games()) as platform:
        monkeypatch.setenv('CHILICHIP_PLATFORM_URL', platform.url)
        assert invoke('login').exit_code == 0
        result = invoke('library')
    assert result.exit_code == 0, result.output
    assert 'Cat Adventure' in result.output


def test_default_platform_url():
    assert chili.platform_url(None) == 'https://platform.chilichip.eu'
    assert chili.platform_url('https://platform-dev.chilichip.eu/') == 'https://platform-dev.chilichip.eu'


# library


def test_library_lists_games_with_the_device_token():
    with FakePlatform(games=library_games()) as platform:
        login(platform)
        result = invoke('library', '--platform', platform.url)
        _, _, headers, _ = platform.requests[-1]
    assert result.exit_code == 0, result.output
    assert headers['Authorization'] == 'Device device-token-123'
    assert 'Cat Adventure' in result.output
    assert 'Drum Night' in result.output
    assert 'Chili Beat' in result.output


def test_library_needs_login():
    with FakePlatform() as platform:
        result = invoke('library', '--platform', platform.url)
    assert result.exit_code == 1
    assert 'Run: chilichip login' in result.output


def test_revoked_device_is_told_to_link_again():
    with FakePlatform(games=library_games()) as platform:
        login(platform)
        platform.revoked = True
        result = invoke('library', '--platform', platform.url)
    assert result.exit_code == 1
    assert 'revoked' in result.output
    assert 'chilichip login' in result.output


# install --from-platform


def install_from_platform(platform, *args):
    console = FakeConsole()
    with mock.patch.object(cli, 'find_console', return_value='/dev/x'), \
            mock.patch.object(cli, 'Console', return_value=console), \
            mock.patch.object(FakeConsole, 'version', return_value=None), \
            mock.patch.object(FakeConsole, 'install') as install:
        result = invoke('install', '--from-platform', '--platform', platform.url, *args)
    return result, install


def test_install_a_game_from_the_library_by_title(config):
    with FakePlatform(games=library_games()) as platform:
        login(platform)
        result, install = install_from_platform(platform, 'cat adventure')
    assert result.exit_code == 0, result.output
    path = install.call_args.args[0]
    assert path.name == 'cat-adventure.bitsy'
    assert path.read_bytes() == BITSY
    assert 'Installed Cat Adventure' in result.output


def test_install_by_id_and_all(config):
    with FakePlatform(games=library_games()) as platform:
        login(platform)
        result, install = install_from_platform(platform, '12')
        assert result.exit_code == 0, result.output
        assert install.call_count == 1

        result, install = install_from_platform(platform, '--all')
    assert result.exit_code == 0, result.output
    assert [c.args[0].name for c in install.call_args_list] == ['cat-adventure.bitsy', 'drum-night.beat']


def test_install_unknown_game():
    with FakePlatform(games=library_games()) as platform:
        login(platform)
        result, install = install_from_platform(platform, 'Space Cat')
    assert result.exit_code == 1
    assert 'No game called "Space Cat" in your library' in result.output
    install.assert_not_called()


def test_install_refuses_a_download_with_the_wrong_checksum():
    games = [{'id': 12, 'title': 'Cat Adventure', 'data': BITSY, 'sha256': '0' * 64}]
    with FakePlatform(games=games) as platform:
        login(platform)
        result, install = install_from_platform(platform, 'Cat Adventure')
    assert result.exit_code == 1
    assert 'checksum' in result.output
    install.assert_not_called()


def test_install_needs_a_game_name():
    with FakePlatform(games=library_games()) as platform:
        login(platform)
        result, install = install_from_platform(platform)
    assert result.exit_code == 2
    assert '--all' in result.output


def test_install_files_still_need_to_exist():
    result = invoke('install', 'missing.blit')
    assert result.exit_code == 2
    assert 'does not exist' in result.output


def test_download_reuses_a_good_copy(config):
    with FakePlatform(games=library_games()) as platform:
        login(platform)
        client = chili.Platform(platform.url, chili.load_token(platform.url))
        game = client.library()[0]
        first = client.download(game)
        downloads = len(platform.requests)
        second = client.download(game)
    assert first == second
    assert len(platform.requests) == downloads


def test_local_name_is_safe():
    game = {'title': '../Cat: Adventure!', 'download_url': '/api/device/games/12.bitsy', 'id': 12}
    assert chili.local_name(game) == 'cat-adventure.bitsy'
    assert chili.local_name({'title': '***', 'download_url': '/api/device/games/3.bitsy', 'id': 3}) == 'game-3.bitsy'


def test_errors_are_chilichip_errors():
    assert issubclass(chili.PlatformError, ChilichipError)


def test_help_lists_platform_commands():
    result = invoke('--help')
    for command in ('login', 'logout', 'library'):
        assert command in result.output


def test_sha256_helper():
    assert chili.sha256(BITSY) == hashlib.sha256(BITSY).hexdigest()


# TUI: the Library tab


def run_tui(check, monkeypatch, url):
    import asyncio

    from chilichip.tui import ChilichipApp
    monkeypatch.setenv('CHILICHIP_PLATFORM_URL', url)

    async def run():
        with mock.patch('chilichip.tui.find_console', side_effect=ChilichipError('No console found.')):
            app = ChilichipApp()
            async with app.run_test() as pilot:
                await app.workers.wait_for_complete()
                await pilot.pause()
                await check(app, pilot)

    asyncio.run(run())


def test_tui_library_tab_when_not_linked(monkeypatch):
    async def check(app, pilot):
        assert 'Not linked' in str(app.query_one('#library-status').render())
        assert app.query_one('#link')

    with FakePlatform() as platform:
        run_tui(check, monkeypatch, platform.url)


def test_tui_library_tab_lists_games(monkeypatch):
    async def check(app, pilot):
        table = app.query_one('#library-games')
        assert table.row_count == 2
        assert 'Cat Adventure' in str(table.get_row_at(0))
        assert 'Linked to' in str(app.query_one('#library-status').render())

    with FakePlatform(games=library_games()) as platform:
        login(platform)
        run_tui(check, monkeypatch, platform.url)


def test_unknown_engine_is_skipped():
    games = [{'id': 3, 'title': 'Robot', 'data': b'x', 'engine': 'robot', 'extension': '.robot'}]
    with FakePlatform(games=games) as platform:
        login(platform)
        result, install = install_from_platform(platform, '--all')
    assert result.exit_code == 0, result.output
    assert 'Skipped Robot' in result.output
    install.assert_not_called()


def test_tui_installs_a_library_game(monkeypatch):
    installed = []

    async def check(app, pilot):
        app.query_one('#tabs').active = 'library'
        await pilot.pause()
        with mock.patch('chilichip.tui.find_console', return_value='/dev/x'), \
                mock.patch('chilichip.tui.Console', return_value=FakeConsole()), \
                mock.patch.object(FakeConsole, 'version', return_value=None), \
                mock.patch.object(FakeConsole, 'games', return_value=[]), \
                mock.patch.object(FakeConsole, 'install', side_effect=lambda path, **kw: installed.append(path.name)):
            await pilot.click('#library-install')
            await app.workers.wait_for_complete()
            await pilot.pause()

    with FakePlatform(games=library_games()) as platform:
        login(platform)
        run_tui(check, monkeypatch, platform.url)
    assert installed == ['cat-adventure.bitsy']


def test_size_text():
    assert chili.size_text(37) == '37 B'
    assert chili.size_text(40960) == '40 KB'


def test_login_stops_waiting_when_cancelled():
    import threading
    stop = threading.Event()
    stop.set()  # the TUI sets this when it quits, so the poll thread can't hold up the exit
    with FakePlatform(polls_before_approval=100) as platform:
        with pytest.raises(chili.PlatformError, match='cancelled'):
            chili.login(platform.url, 'Test PC', echo=lambda line: None, stop=stop)
