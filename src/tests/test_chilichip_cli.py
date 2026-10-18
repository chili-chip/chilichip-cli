import asyncio

import mock
from click.testing import CliRunner

from chilichip import ChilichipError, cli, firmware
from chilichip.console import LoaderVersion
from fakes import FakeConsole


def invoke(*args, **kwargs):
    return CliRunner().invoke(cli.main, args, **kwargs)


def test_help_lists_commands():
    result = invoke('--help')
    assert result.exit_code == 0
    for command in ('update', 'install', 'list', 'delete', 'launch', 'new', 'build', 'run', 'doctor'):
        assert command in result.output


def test_32blit_command_still_works():
    from ttblit import main as blit_main
    result = CliRunner().invoke(blit_main, ['version'])
    assert result.exit_code == 0


def test_errors_are_short():
    with mock.patch.object(cli, 'find_console', side_effect=ChilichipError('No console found.')):
        result = invoke('list')
    assert result.exit_code == 1
    assert 'Error: No console found.' in result.output
    assert 'Traceback' not in result.output


def test_install_wrong_device(test_resources):
    with mock.patch.object(cli, 'find_console', return_value='/dev/x'), \
            mock.patch.object(cli, 'Console', return_value=FakeConsole()):
        result = invoke('install', str(test_resources / 'doom-fire.blit'))
    assert result.exit_code == 1
    assert 'not a ChiliChip game' in result.output


def test_update_up_to_date(tmp_path):
    fw = firmware.Firmware('v1.0.1', tmp_path / 'l.uf2', tmp_path / 'h.blit', tmp_path / 'f.uf2', None)
    console = FakeConsole()
    with mock.patch.object(cli, 'fetch_firmware', return_value=fw), \
            mock.patch.object(cli, 'find_console', return_value='/dev/x'), \
            mock.patch.object(cli, 'Console', return_value=console), \
            mock.patch.object(FakeConsole, 'version', return_value=LoaderVersion('v1.0.1', (0, 6))), \
            mock.patch.object(FakeConsole, 'games', return_value=[]), \
            mock.patch.object(cli, 'make_plan', return_value=firmware.Plan(False, [], [])), \
            mock.patch.object(cli, 'update_console') as update:
        result = invoke('update')
    assert result.exit_code == 0, result.output
    assert 'up to date' in result.output
    update.assert_not_called()


def test_update_asks_first(tmp_path):
    fw = firmware.Firmware('v1.0.1', tmp_path / 'l.uf2', tmp_path / 'h.blit', tmp_path / 'f.uf2', None)
    plan = firmware.Plan(True, [], ['Loader: v1.0.0 -> v1.0.1'])
    with mock.patch.object(cli, 'fetch_firmware', return_value=fw), \
            mock.patch.object(cli, 'find_console', return_value='/dev/x'), \
            mock.patch.object(cli, 'Console', return_value=FakeConsole()), \
            mock.patch.object(FakeConsole, 'version', return_value=None), \
            mock.patch.object(FakeConsole, 'games', return_value=[]), \
            mock.patch.object(cli, 'make_plan', return_value=plan), \
            mock.patch.object(cli, 'update_console') as update:
        result = invoke('update', input='n\n')
        assert 'Loader: v1.0.0 -> v1.0.1' in result.output
        update.assert_not_called()

        result = invoke('update', '--yes')
        assert result.exit_code == 0, result.output
        update.assert_called_once()


def test_build_console(tmp_path):
    with mock.patch.object(cli, 'find_project', return_value=tmp_path), \
            mock.patch.object(cli, 'build', return_value=tmp_path / 'g.blit') as build:
        result = invoke('build', '--console')
    assert result.exit_code == 0, result.output
    build.assert_called_once_with(tmp_path, 'console')


def test_tui_starts_without_console():
    from chilichip.tui import ChilichipApp

    async def run():
        with mock.patch('chilichip.tui.find_console', side_effect=ChilichipError('No console found.')):
            app = ChilichipApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                assert 'No console found' in str(app.query_one('#console-status').render())
                for tab in ('console', 'update', 'new', 'build'):
                    assert app.query_one(f'#{tab}')

    asyncio.run(run())
