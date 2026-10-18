import pathlib
import struct

import mock
import pytest

from chilichip import ChilichipError
from chilichip.console import (BlitInfo, LoaderVersion, check_blit,
                               find_bootsel_drive, find_console, read_blit)
from fakes import Comport, FakeConsole
from ttblit.core.blitserial import BlitSerial


def comports():
    return [Comport(0, 0, 'notblit'), Comport(0xCAFE, 0x4003, '/dev/ttyACM7')]


def test_find_console():
    with mock.patch('serial.tools.list_ports.comports', return_value=comports()):
        assert find_console() == '/dev/ttyACM7'


def test_find_console_missing():
    with mock.patch('serial.tools.list_ports.comports', return_value=[Comport(0, 0, 'x')]):
        with pytest.raises(ChilichipError, match='No console found'):
            find_console()


def test_32blit_tool_finds_the_console():
    with mock.patch('serial.tools.list_ports.comports', return_value=comports()):
        assert BlitSerial.find_comport() == ['/dev/ttyACM7']
    with mock.patch('serial.tools.list_ports.comports', return_value=comports()):
        assert BlitSerial.validate_comport('/dev/ttyACM7') == ['/dev/ttyACM7']


def test_version():
    c = FakeConsole(b'32BLVERS' + b'v1.0.1\x00' + struct.pack('<HH', 0, 6))
    assert c.version() == LoaderVersion('v1.0.1', (0, 6))
    # the loader only runs a command once the byte after its 8 byte header arrives
    assert c.sent() == b'32BLVERS\x00'


def test_version_old_loader():
    # older loaders print the unknown command; the line must not reach the next reply
    c = FakeConsole(b'got: 32BLVERS\r\n32BL__OK')
    assert c.version() is None
    assert c.read(8) == b'32BL__OK'


def test_version_no_answer():
    assert FakeConsole(b'').version() is None


def test_read_blit(test_resources):
    info = read_blit(test_resources / 'doom-fire-vgc.blit')
    assert info.device_id == 3
    assert info.api == (0, 6)
    assert info.title == 'Doom Fire'
    assert info.author
    assert info.checksum


def test_read_blit_not_a_blit(tmp_path):
    f = tmp_path / 'x.blit'
    f.write_bytes(b'hello world, this is not a game at all')
    with pytest.raises(ChilichipError, match='not a .blit'):
        read_blit(f)


def test_check_blit_rejects_32blit_build(test_resources):
    info = read_blit(test_resources / 'doom-fire.blit')
    with pytest.raises(ChilichipError, match='not a ChiliChip game'):
        check_blit(info, 'doom-fire.blit')


def test_check_blit_needs_system_update():
    info = BlitInfo(3, (0, 7), 'game', 'me', 'v1', 1)
    check_blit(info, 'game.blit')  # unknown loader API: allowed
    check_blit(info, 'game.blit', (0, 7))
    with pytest.raises(ChilichipError, match='system update'):
        check_blit(info, 'game.blit', (0, 6))
    with pytest.raises(ChilichipError, match='system update'):
        check_blit(info, 'game.blit', (1, 9))


def test_install_blit(test_resources):
    path = test_resources / 'doom-fire-vgc.blit'
    c = FakeConsole(b'32BL__OK\x05\x00')
    c.install(path, launch=True)
    size = path.stat().st_size
    assert c.sent() == b'32BLPROGdoom-fire-vgc.blit\x00%d\x00' % size + path.read_bytes() + b'32BLLNCHflash:/5\x00'


def test_install_refuses_wrong_device(test_resources):
    c = FakeConsole(b'32BL__OK\x00\x00')
    with pytest.raises(ChilichipError):
        c.install(test_resources / 'doom-fire.blit')
    assert c.sent() == b''


def test_install_bitsy(tmp_path):
    game = tmp_path / 'cat.bitsy'
    game.write_text('cat game')
    c = FakeConsole(b'32BL__OK')
    c.install(game)
    assert c.sent() == b'32BLSAVE/bitsy-games/cat.bitsy\x008\x00cat game'


def test_install_other_files(tmp_path):
    with pytest.raises(ChilichipError, match='.blit and .bitsy'):
        FakeConsole().install(tmp_path / 'notes.txt')


def test_install_failure_is_readable(test_resources):
    c = FakeConsole(b'')
    with pytest.raises(ChilichipError, match='Failed'):
        c.install(test_resources / 'doom-fire-vgc.blit')


def test_games(test_resources):
    data = (test_resources / 'doom-fire-vgc.blit').read_bytes()
    end, = struct.unpack_from('<I', data, 16)
    meta = data[end & 0x1FFFFFF:]
    reply = struct.pack('<II', 0x50000, end & 0x1FFFFFF) + meta + b'\xff\xff\xff\xff'
    games = FakeConsole(reply).games()
    assert len(games) == 1
    assert games[0].block == 5
    assert games[0].title == 'Doom Fire'
    assert games[0].checksum == read_blit(test_resources / 'doom-fire-vgc.blit').checksum


def test_games_timeout():
    # a console that stops answering mid-list must not hang or crash
    assert FakeConsole(b'').games() == []


def test_delete_and_launch():
    c = FakeConsole()
    c.delete(3)
    c.launch_block(2)
    assert c.sent() == b'32BLERSE\x00\x00\x03\x00\x0032BLLNCHflash:/2\x00'


def drive(root, name, board):
    d = root / name
    d.mkdir(parents=True)
    (d / 'INFO_UF2.TXT').write_text(f'UF2 Bootloader v1.0\nModel: Raspberry Pi RP2\nBoard-ID: {board}\n')
    return d


def test_find_bootsel_drive(tmp_path):
    drive(tmp_path, 'RPI-RP2', 'RPI-RP2')
    (tmp_path / 'CHILICHIP').mkdir()
    rp2350 = drive(tmp_path, 'RP2350', 'RP2350')
    assert find_bootsel_drive([tmp_path, tmp_path / 'missing']) == rp2350


def test_find_bootsel_drive_none(tmp_path):
    assert find_bootsel_drive([tmp_path]) is None


def test_open_error_is_readable():
    with pytest.raises(ChilichipError, match='Cannot open'):
        from chilichip.console import Console
        Console(str(pathlib.Path('/dev/does-not-exist')))
