"""Game projects: create one from a template, build it and run it on the desktop or the console."""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass

import click

from . import ChilichipError
from .console import Console, find_console

TEMPLATES = {
    'game': 'https://github.com/chili-chip/game-template',
    'rpg': 'https://github.com/chili-chip/rpg-template',
}
SDKS = ('32blit-sdk', 'pico-sdk', 'pico-extras')  # cloned next to the game, see "Install the tools"
PRESETS = {'desktop': 'linux', 'console': 'vgc-blit'}  # the template's CMake presets

NAME_RE = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,23}')  # a CMake target and a 24 character title
PROJECT_RE = re.compile(r'^(project\(\s*)([^\s)]+)', re.MULTILINE)
AUTHOR_LENGTH = 16  # the .blit metadata field holds 16 characters


def run(cmd, cwd=None, log=None):
    """Run a command. Output goes to the terminal, or line by line to log."""
    try:
        if log is None:
            code = subprocess.run(cmd, cwd=cwd).returncode
        else:
            with subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors='replace') as p:
                for line in p.stdout:
                    log(line.rstrip())
                code = p.wait()
    except FileNotFoundError:
        raise ChilichipError(f'{cmd[0]} is not installed. Run: chilichip doctor')
    if code:
        raise ChilichipError(f'{" ".join(cmd[:2])} failed (exit code {code}).')


def check_name(name):
    if not NAME_RE.fullmatch(name):
        raise ChilichipError(
            f'"{name}" is not a valid game name: use up to 24 letters, digits, - or _, starting with a letter.')


def git_user():
    try:
        result = subprocess.run(['git', 'config', 'user.name'], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return result.stdout.strip() or None


def project_name(folder):
    match = PROJECT_RE.search((pathlib.Path(folder) / 'CMakeLists.txt').read_text())
    if not match:
        raise ChilichipError(f'No project() line in {folder}/CMakeLists.txt.')
    return match.group(2)


def rename_project(folder, name, author):
    """Set the CMake project name, and the title and author in metadata.yml."""
    cmake = folder / 'CMakeLists.txt'
    cmake.write_text(PROJECT_RE.sub(lambda m: m.group(1) + name, cmake.read_text(), count=1))

    meta = folder / 'metadata.yml'
    text = meta.read_text()
    # edit the lines in place to keep the template's comments
    text = re.sub(r'^title:.*$', f'title: {name}', text, count=1, flags=re.MULTILINE)
    author = json.dumps(author[:AUTHOR_LENGTH])  # a JSON string is a valid YAML string
    text = re.sub(r'^author:.*$', lambda m: f'author: {author}', text, count=1, flags=re.MULTILINE)
    meta.write_text(text)


def remove_tree(path):
    def make_writable(func, p, _):  # git marks its objects read-only, which Windows refuses to delete
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=make_writable)


def new_project(name, template='game', parent=None, author=None, url=None, log=click.echo):
    """Copy a template into parent/name, rename it and start a fresh git repository."""
    check_name(name)
    parent = pathlib.Path(parent or pathlib.Path.cwd())
    folder = parent / name
    if folder.exists():
        raise ChilichipError(f'{folder} already exists.')

    run(['git', 'clone', '--depth', '1', '--quiet', url or TEMPLATES[template], str(folder)], log=log)
    remove_tree(folder / '.git')
    rename_project(folder, name, author or git_user() or 'you')

    run(['git', 'init', '--quiet'], cwd=folder, log=log)
    run(['git', 'add', '--all'], cwd=folder, log=log)
    try:
        run(['git', 'commit', '--quiet', '-m', f'New game from the {template} template'], cwd=folder, log=log)
    except ChilichipError:
        log('Skipped the first commit. Set git user.name and user.email, then commit yourself.')
    return folder


def missing_sdks(parent):
    return [sdk for sdk in SDKS if not (pathlib.Path(parent) / sdk).is_dir()]


def clone_command(sdk, parent):
    cmd = ['git', 'clone', f'https://github.com/chili-chip/{sdk}', str(pathlib.Path(parent) / sdk)]
    if sdk == 'pico-sdk':
        cmd.insert(2, '--recurse-submodules')
    return cmd


def clone_sdks(sdks, parent, log=None):
    for sdk in sdks:
        run(clone_command(sdk, parent), log=log)


def find_project(start=None):
    """The game project that holds start (default: the current folder)."""
    start = pathlib.Path(start or pathlib.Path.cwd()).resolve()
    for folder in (start, *start.parents):
        if (folder / 'CMakeLists.txt').is_file() and (folder / 'metadata.yml').is_file():
            return folder
    raise ChilichipError('This is not a game project. Go to your game folder, or start one with: chilichip new NAME')


def build_dir(folder, target):
    return folder / 'out' / 'build' / PRESETS[target]


def presets(folder):
    try:
        data = json.loads((folder / 'CMakePresets.json').read_text())
    except (OSError, ValueError):
        return set()
    return {p.get('name') for p in data.get('configurePresets', [])}


def configure_command(folder, target):
    """Use the project's preset; projects without one get the same settings on the command line."""
    preset = PRESETS[target]
    if preset in presets(folder):
        return ['cmake', '--preset', preset]

    cmd = ['cmake', '-S', str(folder), '-B', str(build_dir(folder, target)), '-DCMAKE_BUILD_TYPE=Debug']
    if target == 'console':
        sdk = folder.parent / '32blit-sdk'
        cmd += [
            f'-D32BLIT_DIR={sdk}',
            f'-DPICO_SDK_PATH={folder.parent / "pico-sdk"}',
            '-DPICO_BOARD=chilichip_vgc',
            '-DPICO_PLATFORM=rp2350-arm-s',
            f'-DCMAKE_TOOLCHAIN_FILE={sdk / "pico2.toolchain"}',
            '-DBLIT_EXECUTABLE_PICO_BLIT=1',
        ]
    return cmd


def output_path(folder, target):
    out = build_dir(folder, target)
    name = project_name(folder)
    names = [f'{name}.blit'] if target == 'console' else [f'{name}.elf', name, f'{name}.exe']
    for n in names:
        if (out / n).is_file():
            return out / n
    raise ChilichipError(f'The build finished, but there is no {names[0]} in {out}.')


def build(folder, target, log=None):
    """Configure (first time only) and build. Returns the game file."""
    if not (build_dir(folder, target) / 'CMakeCache.txt').exists():
        run(configure_command(folder, target), cwd=folder, log=log)
    run(['cmake', '--build', str(build_dir(folder, target)), '--parallel'], cwd=folder, log=log)
    return output_path(folder, target)


def run_game(folder, target, log=None):
    """Build, then start the game on the desktop, or install and launch it on the console."""
    game = build(folder, target, log)
    if target == 'desktop':
        run([str(game)], cwd=game.parent, log=log)
        return
    port = find_console()
    with Console(port) as console:
        version = console.version()
        console.install(game, launch=True, loader_api=version.api if version else None)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str  # what was found, or how to fix it


def doctor(folder=None, which=shutil.which, find_console=find_console):
    """Check the tools and SDKs needed to build games, and the console."""
    folder = pathlib.Path(folder or pathlib.Path.cwd())
    try:
        root = find_project(folder).parent
    except ChilichipError:
        root = folder

    def tool(name, commands, fix):
        found = next((which(c) for c in commands if which(c)), None)
        return Check(name, bool(found), found or fix)

    checks = [
        tool('CMake', ['cmake'], 'Install CMake 3.15 or newer: sudo apt install cmake, or brew install cmake'),
        tool('Git', ['git'], 'sudo apt install git, or brew install git'),
        tool('C++ compiler', ['g++', 'clang++', 'c++'], 'sudo apt install g++, or xcode-select --install'),
        tool('SDL2', ['sdl2-config'],
             'sudo apt install libsdl2-dev libsdl2-image-dev libsdl2-net-dev, or brew install sdl2 sdl2_image sdl2_net'),
        tool('Arm toolchain', ['arm-none-eabi-gcc'],
             'sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib, '
             'or brew install --cask gcc-arm-embedded'),
        tool('32blit tool', ['32blit'], 'pipx install chilichip (it includes the 32blit command)'),
    ]
    for sdk in SDKS:
        path = root / sdk
        checks.append(Check(sdk, path.is_dir(), str(path) if path.is_dir() else ' '.join(clone_command(sdk, root))))

    try:
        checks.append(Check('Console', True, find_console()))
    except ChilichipError as e:
        checks.append(Check('Console', False, e.message))
    return checks
