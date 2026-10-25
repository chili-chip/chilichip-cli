"""Download the latest console firmware and install it: loader, home screen and Bitsy player."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import pathlib
import re
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass, field

import click

from . import ChilichipError
from .console import (Console, find_bootsel_drive, find_console, read_blit,
                      reboot_to_bootsel, wait_for)

SDK_REPO = 'chili-chip/32blit-sdk'
PLAYER_REPO = 'chili-chip/citsy-32blit'
SDK_ASSET = '*-VGC-blit.zip'
PLAYER_ASSET = '*.blit'


@dataclass
class Firmware:
    version: str  # the 32blit-sdk release tag
    loader: pathlib.Path  # blit-loader.uf2
    home: pathlib.Path  # vgc-os.blit, the home screen
    factory: pathlib.Path  # vgc-os-factory.uf2, loader + home screen
    player: pathlib.Path | None  # the Bitsy player, when its release has a .blit


@dataclass
class Plan:
    loader: bool
    blits: list = field(default_factory=list)
    lines: list = field(default_factory=list)  # what changes, for the user


def cache_dir():
    return pathlib.Path(click.get_app_dir('chilichip')) / 'cache'


def latest_release(repo):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/releases/latest',
        headers={'Accept': 'application/vnd.github+json'})
    token = os.environ.get('GITHUB_TOKEN')
    if token:  # optional, only to avoid the API rate limit
        request.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except OSError as e:
        raise ChilichipError(f'Cannot reach GitHub to check for {repo} releases: {e}')


def find_asset(release, pattern):
    return next((a for a in release.get('assets', []) if fnmatch.fnmatch(a['name'], pattern)), None)


def sha256_ok(path, digest):
    if not digest:
        return True  # older releases have no digest
    algorithm, _, expected = digest.partition(':')
    return hashlib.new(algorithm, path.read_bytes()).hexdigest() == expected


def download(asset, folder):
    """Download a release asset into folder and check its sha256. Reuses a good copy."""
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / asset['name']
    digest = asset.get('digest')
    if path.exists() and sha256_ok(path, digest):
        return path

    part = path.with_name(path.name + '.part')
    try:
        with urllib.request.urlopen(asset['browser_download_url'], timeout=60) as response, open(part, 'wb') as f:
            shutil.copyfileobj(response, f)
    except OSError as e:
        part.unlink(missing_ok=True)
        raise ChilichipError(f'Download of {asset["name"]} failed: {e}')

    if not sha256_ok(part, digest):
        part.unlink()
        raise ChilichipError(f'{asset["name"]}: the download is damaged (sha256 does not match). Try again.')
    part.replace(path)
    return path


def extract(archive, name, folder):
    """Copy the file called name (in any folder of the zip) to folder."""
    with zipfile.ZipFile(archive) as z:
        member = next((m for m in z.namelist() if m.rsplit('/', 1)[-1] == name), None)
        if member is None:
            raise ChilichipError(f'{archive.name} has no {name}.')
        path = folder / name
        path.write_bytes(z.read(member))
        return path


def fetch_firmware(folder=None, log=click.echo):
    """Download the latest firmware files into the cache."""
    folder = pathlib.Path(folder or cache_dir())

    release = latest_release(SDK_REPO)
    asset = find_asset(release, SDK_ASSET)
    if asset is None:
        raise ChilichipError(f'{SDK_REPO} {release["tag_name"]} has no {SDK_ASSET} file.')
    log(f'Latest firmware: {release["tag_name"]}')
    archive = download(asset, folder)

    out = folder / release['tag_name']
    out.mkdir(exist_ok=True)
    loader, home, factory = (extract(archive, n, out) for n in ('blit-loader.uf2', 'vgc-os.blit', 'vgc-os-factory.uf2'))

    player = None
    player_release = latest_release(PLAYER_REPO)
    player_asset = find_asset(player_release, PLAYER_ASSET)
    if player_asset:
        player = download(player_asset, folder / f'citsy-32blit-{player_release["tag_name"]}')
    else:
        log(f'The Bitsy player release {player_release["tag_name"]} has no .blit file yet, skipping it.')

    return Firmware(release['tag_name'], loader, home, factory, player)


def parse_version(text):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', text or '')
    return tuple(int(x) for x in match.groups()) if match else None


def loader_is_current(console_version, latest):
    """A loader that doesn't report a release version (old or local build) counts as out of date."""
    current, wanted = parse_version(console_version), parse_version(latest)
    return current is not None and wanted is not None and current >= wanted


def make_plan(firmware, loader_version, games, force=False):
    """Work out what an update changes on this console."""
    plan = Plan(loader=force or not loader_is_current(loader_version and loader_version.version, firmware.version))
    if plan.loader:
        current = loader_version.version if loader_version else 'unknown'
        plan.lines.append(f'Loader: {current} -> {firmware.version}')

    for path in (firmware.home, firmware.player):
        if path is None:
            continue
        info = read_blit(path)
        old = next((g for g in games if (g.title, g.author) == (info.title, info.author)), None)
        if old and old.checksum == info.checksum and not force:
            continue
        before = old.version if old else 'not installed'
        plan.lines.append(f'{info.title}: {before} -> {info.version}')
        plan.blits.append(path)

    return plan


def copy_uf2(uf2, drive):
    try:
        shutil.copyfile(uf2, drive / uf2.name)
    except OSError:
        if drive.exists():
            raise
        # the console restarts as soon as it has the whole file, which can unmount the drive mid-close


def flash_uf2(uf2, port, log=click.echo):
    """Copy a .uf2 in BOOTSEL mode and wait for the console to come back. Returns its new port."""
    if port:
        log('Restarting the console into BOOTSEL mode...')
        reboot_to_bootsel(port)
        drive = wait_for(find_bootsel_drive, 10)
    else:
        drive = find_bootsel_drive()
    if drive is None:
        log('Switch the console off, then hold X and switch it on.')
        drive = wait_for(find_bootsel_drive, 120)
    if drive is None:
        raise ChilichipError('No RP2350 drive found. Hold X while switching the console on, then run the command again.')

    log(f'Copying {uf2.name} to {drive}...')
    copy_uf2(uf2, drive)

    port = wait_for(find_console, 30)
    if port is None:
        raise ChilichipError('The console did not come back. Switch it off and on, then run chilichip update again.')
    return port


def install_all(port, blits, log=click.echo):
    with Console(port) as console:
        for path in blits:
            log(f'Installing {path.name}...')
            console.install(path)


def update_console(firmware, plan, port, log=click.echo):
    if plan.loader:
        port = flash_uf2(firmware.loader, port, log)
    install_all(port, plan.blits, log)
    log(f'Done. The console runs {firmware.version}.')


def factory_install(firmware, port=None, log=click.echo):
    """Set up a new or wiped console: loader and home screen in one .uf2, then the Bitsy player."""
    port = flash_uf2(firmware.factory, port, log)
    install_all(port, [firmware.player] if firmware.player else [], log)
    log(f'Done. The console runs {firmware.version}.')
