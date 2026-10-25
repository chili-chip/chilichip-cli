import json
import subprocess

import mock
import pytest

from chilichip import ChilichipError, project

CMAKELISTS = '''cmake_minimum_required(VERSION 3.15)

# Replace "game" with a name for your project
project(game LANGUAGES C CXX ASM)
blit_executable (${PROJECT_NAME} game.cpp)
'''

METADATA = '''title: game title
description: game description
author: you
version: v0.0.1
category: game # game, demo, utility, ...
'''


def make_template(path):
    path.mkdir()
    (path / 'CMakeLists.txt').write_text(CMAKELISTS)
    (path / 'metadata.yml').write_text(METADATA)
    git = ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com']
    subprocess.run(['git', 'init', '-q'], cwd=path, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=path, check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'upstream history'], cwd=path, check=True)
    return path


@pytest.mark.parametrize('name', ['my-game', 'Snake2', 'a_b'])
def test_valid_names(name):
    project.check_name(name)


@pytest.mark.parametrize('name', ['', '2fast', 'my game', '../evil', 'a' * 25])
def test_invalid_names(name):
    with pytest.raises(ChilichipError):
        project.check_name(name)


def test_rename_project(tmp_path):
    (tmp_path / 'CMakeLists.txt').write_text(CMAKELISTS)
    (tmp_path / 'metadata.yml').write_text(METADATA)
    project.rename_project(tmp_path, 'space-cat', 'Ada: "L"')

    cmake = (tmp_path / 'CMakeLists.txt').read_text()
    assert 'project(space-cat LANGUAGES C CXX ASM)' in cmake
    assert 'Replace "game"' in cmake
    assert project.project_name(tmp_path) == 'space-cat'

    import yaml
    meta = yaml.safe_load((tmp_path / 'metadata.yml').read_text())
    assert meta['title'] == 'space-cat'
    assert meta['author'] == 'Ada: "L"'
    assert meta['category'] == 'game'


def test_rename_truncates_long_author(tmp_path):
    (tmp_path / 'CMakeLists.txt').write_text(CMAKELISTS)
    (tmp_path / 'metadata.yml').write_text(METADATA)
    project.rename_project(tmp_path, 'x', 'A very long author name')
    import yaml
    assert yaml.safe_load((tmp_path / 'metadata.yml').read_text())['author'] == 'A very long auth'


def test_new_project(tmp_path, monkeypatch):
    for var in ('GIT_AUTHOR_NAME', 'GIT_COMMITTER_NAME'):
        monkeypatch.setenv(var, 'Ada')
    for var in ('GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_EMAIL'):
        monkeypatch.setenv(var, 'ada@example.com')
    template = make_template(tmp_path / 'template')
    dest = project.new_project('my-game', parent=tmp_path, author='Ada', url=template.as_uri(), log=lambda *a: None)

    assert dest == tmp_path / 'my-game'
    assert project.project_name(dest) == 'my-game'
    log = subprocess.run(['git', 'log', '--oneline'], cwd=dest, capture_output=True, text=True).stdout
    assert 'upstream history' not in log  # template history is dropped
    assert len(log.splitlines()) == 1


def test_new_project_refuses_existing_folder(tmp_path):
    (tmp_path / 'my-game').mkdir()
    with pytest.raises(ChilichipError, match='already exists'):
        project.new_project('my-game', parent=tmp_path, url='unused')


def test_missing_sdks(tmp_path):
    (tmp_path / '32blit-sdk').mkdir()
    assert project.missing_sdks(tmp_path) == ['pico-sdk', 'pico-extras']


def game(tmp_path, presets=None):
    d = tmp_path / 'my-game'
    d.mkdir()
    (d / 'CMakeLists.txt').write_text(CMAKELISTS.replace('project(game', 'project(my-game'))
    (d / 'metadata.yml').write_text(METADATA)
    if presets:
        (d / 'CMakePresets.json').write_text(json.dumps({'configurePresets': [{'name': p} for p in presets]}))
    return d


def test_configure_uses_preset(tmp_path):
    d = game(tmp_path, ['linux', 'vgc-blit'])
    assert project.configure_command(d, 'console') == ['cmake', '--preset', 'vgc-blit']
    assert project.configure_command(d, 'desktop') == ['cmake', '--preset', 'linux']


def test_configure_without_preset(tmp_path):
    d = game(tmp_path)
    cmd = project.configure_command(d, 'console')
    assert cmd[:5] == ['cmake', '-S', str(d), '-B', str(d / 'out' / 'build' / 'vgc-blit')]
    assert '-DPICO_BOARD=chilichip_vgc' in cmd
    assert f'-DPICO_SDK_PATH={tmp_path / "pico-sdk"}' in cmd
    assert project.configure_command(d, 'desktop')[:5] == ['cmake', '-S', str(d), '-B', str(d / 'out' / 'build' / 'linux')]


def test_build(tmp_path):
    d = game(tmp_path, ['linux', 'vgc-blit'])
    out = d / 'out' / 'build' / 'vgc-blit'

    def fake_run(cmd, cwd=None, log=None):
        if cmd[1] == '--preset':
            out.mkdir(parents=True)
            (out / 'CMakeCache.txt').write_text('')
        else:
            (out / 'my-game.blit').write_bytes(b'BLIT')

    with mock.patch.object(project, 'run', side_effect=fake_run) as run:
        assert project.build(d, 'console') == out / 'my-game.blit'
        assert run.call_count == 2
        # configured once, after that only builds
        project.build(d, 'console')
        assert run.call_count == 3
        assert run.call_args[0][0][:2] == ['cmake', '--build']


def test_build_output_missing(tmp_path):
    d = game(tmp_path, ['linux'])
    with mock.patch.object(project, 'run'):
        with pytest.raises(ChilichipError, match='no my-game'):
            project.build(d, 'desktop')


def test_desktop_output(tmp_path):
    d = game(tmp_path)
    out = d / 'out' / 'build' / 'linux'
    out.mkdir(parents=True)
    (out / 'my-game.elf').write_text('')
    assert project.output_path(d, 'desktop') == out / 'my-game.elf'


def test_find_project(tmp_path):
    d = game(tmp_path)
    (d / 'assets').mkdir()
    assert project.find_project(d / 'assets') == d
    with pytest.raises(ChilichipError, match='game project'):
        project.find_project(tmp_path)


def test_run_reports_missing_tool():
    with pytest.raises(ChilichipError, match='not installed'):
        project.run(['definitely-not-a-real-tool-xyz'])


def test_run_reports_failure():
    with pytest.raises(ChilichipError, match='failed'):
        project.run(['git', 'not-a-git-command'], log=lambda *a: None)


def test_run_streams_to_log():
    lines = []
    project.run(['git', '--version'], log=lines.append)
    assert lines and lines[0].startswith('git version')


def test_doctor(tmp_path):
    d = game(tmp_path)
    (tmp_path / '32blit-sdk').mkdir()

    def which(name):
        return None if name in ('arm-none-eabi-gcc', 'sdl2-config') else f'/usr/bin/{name}'

    def no_console():
        raise ChilichipError('No console found.')

    checks = {c.name: c for c in project.doctor(d, which=which, find_console=no_console)}
    assert checks['CMake'].ok
    assert not checks['Arm toolchain'].ok
    assert 'gcc-arm-none-eabi' in checks['Arm toolchain'].detail
    assert checks['32blit-sdk'].ok
    assert not checks['pico-sdk'].ok
    assert 'git clone' in checks['pico-sdk'].detail
    assert not checks['Console'].ok
