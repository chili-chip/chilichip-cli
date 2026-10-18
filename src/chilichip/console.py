"""Talk to a ChiliChip console over USB: find it, read versions, install and manage games."""
from __future__ import annotations

import getpass
import os
import pathlib
import string
import struct
import time
from dataclasses import dataclass

import serial
import serial.tools.list_ports
from construct.core import ConstructError

from ttblit.core.blitserial import BlitSerial
from ttblit.core.struct import struct_blit_meta_standalone

from . import ChilichipError

CONSOLE_USB_ID = (0xCAFE, 0x4003)  # the loader's TinyUSB CDC + MSC device
BLOCK_SIZE = 64 * 1024  # games are installed at 64 KB flash blocks
DEVICE_RP2350 = 3  # BlitDevice::RP2350 in launcher-shared/executable.hpp
DEVICE_NAMES = {0: '32Blit (old header)', 1: '32Blit', 2: 'RP2040', 3: 'RP2350'}
BITSY_FOLDER = '/bitsy-games'  # the Bitsy player lists .bitsy files from here


@dataclass(frozen=True)
class LoaderVersion:
    version: str  # release tag, for example "v1.0.1"
    api: tuple


@dataclass(frozen=True)
class BlitInfo:
    device_id: int
    api: tuple
    title: str
    author: str
    version: str
    checksum: int | None


@dataclass(frozen=True)
class InstalledGame:
    block: int
    size: int
    title: str
    author: str
    version: str
    checksum: int | None


def find_console():
    """Return the serial port of the first connected console."""
    for port in serial.tools.list_ports.comports():
        if (port.vid, port.pid) == CONSOLE_USB_ID:
            return port.device
    raise ChilichipError('No console found. Connect it with a USB cable and switch it on.')


def read_blit(path):
    """Read the header and metadata of a .blit file."""
    path = pathlib.Path(path)
    data = path.read_bytes()

    start = 0
    if data[:4] == b'RELO':  # 32Blit games start with a relocation table
        count, = struct.unpack_from('<I', data, 4)
        start = 8 + count * 4

    if len(data) < start + 28 or data[start:start + 4] != b'BLIT':
        raise ChilichipError(f'{path.name} is not a .blit file.')

    end, device_id = struct.unpack_from('<IB', data, start + 16)
    api = struct.unpack_from('<HH', data, start + 24) if device_id else (0, 0)

    title = author = version = ''
    checksum = None
    meta_start = start + (end & 0x1FFFFFF)
    if device_id == DEVICE_RP2350 and data[meta_start:meta_start + 8] == b'BLITMETA':
        try:
            meta = struct_blit_meta_standalone.parse(data[meta_start:]).data
            title, author, version, checksum = meta.title, meta.author, meta.version, meta.checksum
        except ConstructError:
            pass

    return BlitInfo(device_id, tuple(api), title, author, version, checksum)


def check_blit(info, name, loader_api=None):
    """Refuse files the console would reject, with the reason and the fix."""
    if info.device_id != DEVICE_RP2350:
        device = DEVICE_NAMES.get(info.device_id, f'device {info.device_id}')
        raise ChilichipError(
            f'{name} is not a ChiliChip game: it was built for {device}. '
            'Build it with the vgc-blit preset from a clean build folder.')

    if loader_api and (info.api[0] != loader_api[0] or info.api[1] > loader_api[1]):
        raise ChilichipError(
            f'{name} needs a system update: it uses API {info.api[0]}.{info.api[1]}, '
            f'the console has {loader_api[0]}.{loader_api[1]}. Run: chilichip update')


class Console(BlitSerial):
    """A connected console running the ChiliChip loader."""

    def __init__(self, port):
        try:
            super().__init__(port)
        except serial.SerialException as e:
            hint = ''
            if os.name == 'posix' and 'ermission' in str(e):
                hint = ' Add yourself to the dialout group (sudo usermod -aG dialout $USER), then log out and in.'
            raise ChilichipError(f'Cannot open {port}: {e}.{hint}')

    def version(self):
        """Ask the loader for its version. Older loaders do not answer and give None."""
        self.reset_input_buffer()
        self.write(b'32BLVERS')
        timeout, self.timeout = self.timeout, 1
        try:
            if self.read(8) != b'32BLVERS':
                return None
            raw = bytearray()
            while len(raw) < 64:
                c = self.read(1)
                if c in (b'', b'\x00'):
                    break
                raw += c
            api = self.read(4)
            if len(api) != 4:
                return None
        finally:
            self.timeout = timeout
        return LoaderVersion(raw.decode('ascii', 'replace'), struct.unpack('<HH', api))

    def games(self):
        """List the games installed in flash, the home screen and the Bitsy player included."""
        return [
            InstalledGame(
                block=offset // BLOCK_SIZE,
                size=size,
                title=meta.data.title if meta else '',
                author=meta.data.author if meta else '',
                version=meta.data.version if meta else '',
                checksum=meta.data.checksum if meta else None,
            )
            for meta, offset, size in self.list()
        ]

    def install(self, path, launch=False, loader_api=None):
        """Install a .blit into flash, or copy a .bitsy for the Bitsy player."""
        path = pathlib.Path(path)
        suffix = path.suffix.lower()
        if suffix == '.blit':
            check_blit(read_blit(path), path.name, loader_api)
            drive, folder = 'flash', pathlib.PurePosixPath('/')
        elif suffix == '.bitsy':
            drive, folder = 'sd', pathlib.PurePosixPath(BITSY_FOLDER)
        else:
            raise ChilichipError(f'{path.name}: only .blit and .bitsy files can be installed.')

        try:
            self.send_file(path, drive, folder, auto_launch=launch)
        except RuntimeError as e:
            raise ChilichipError(str(e))

    def delete(self, block):
        self.erase(block * BLOCK_SIZE)

    def launch_block(self, block):
        self.launch(f'flash:/{block}')


def reboot_to_bootsel(port):
    """Ask the loader to restart into the RP2350 USB bootloader (the 1200 baud touch)."""
    try:
        serial.Serial(port, baudrate=1200).close()
    except serial.SerialException:
        pass  # the console drops off the bus while we close the port


def mount_roots():
    """Folders that removable drives get mounted under."""
    if os.name == 'nt':
        return []
    user = getpass.getuser()
    return [pathlib.Path(p) for p in (f'/media/{user}', f'/run/media/{user}', '/media', '/Volumes', '/mnt')]


def drive_candidates(roots):
    if roots is None and os.name == 'nt':
        yield from (pathlib.Path(f'{letter}:/') for letter in string.ascii_uppercase)
        return
    for root in mount_roots() if roots is None else roots:
        try:
            yield from (p for p in root.iterdir() if p.is_dir())
        except OSError:
            continue


def find_bootsel_drive(roots=None):
    """Return the mounted RP2350 BOOTSEL drive, or None."""
    for drive in drive_candidates(roots):
        try:
            if 'RP2350' in (drive / 'INFO_UF2.TXT').read_text(errors='replace'):
                return drive
        except OSError:
            continue
    return None


def wait_for(check, timeout, interval=0.5):
    """Call check() until it returns something, or give up after timeout seconds."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            result = check()
            if result:
                return result
        except ChilichipError:
            pass
        if time.monotonic() >= deadline:
            return None
        time.sleep(interval)
