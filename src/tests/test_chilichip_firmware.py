import hashlib
import io
import zipfile

import mock
import pytest

from chilichip import ChilichipError, firmware
from chilichip.console import InstalledGame, LoaderVersion, read_blit
from fakes import FakeConsole


def asset(name, data):
    return {
        'name': name,
        'browser_download_url': f'https://example.com/{name}',
        'digest': 'sha256:' + hashlib.sha256(data).hexdigest(),
    }


def fake_urlopen(files):
    """urlopen() stand-in serving {url: bytes}."""
    def urlopen(request, timeout=None):
        url = getattr(request, 'full_url', request)
        return io.BytesIO(files[url])
    return urlopen


def test_parse_version():
    assert firmware.parse_version('v1.0.1') == (1, 0, 1)
    assert firmware.parse_version('1.2.3') == (1, 2, 3)
    assert firmware.parse_version('v1.0.1-3-gabcdef') is None
    assert firmware.parse_version('DEV') is None
    assert firmware.parse_version(None) is None


def test_loader_is_current():
    assert firmware.loader_is_current('v1.0.1', 'v1.0.1')
    assert firmware.loader_is_current('v1.0.2', 'v1.0.1')
    assert not firmware.loader_is_current('v1.0.0', 'v1.0.1')
    assert not firmware.loader_is_current('v1.0.1-2-gabc', 'v1.0.1')
    assert not firmware.loader_is_current(None, 'v1.0.1')


def test_find_asset():
    release = {'assets': [asset('32blit-sdk-v1.0.1-VGC.zip', b''), asset('32blit-sdk-v1.0.1-VGC-blit.zip', b'')]}
    assert firmware.find_asset(release, '*-VGC-blit.zip')['name'] == '32blit-sdk-v1.0.1-VGC-blit.zip'
    assert firmware.find_asset(release, '*.blit') is None


def test_download_checks_digest(tmp_path):
    good = asset('a.zip', b'payload')
    with mock.patch('urllib.request.urlopen', fake_urlopen({good['browser_download_url']: b'payload'})):
        path = firmware.download(good, tmp_path)
    assert path.read_bytes() == b'payload'

    bad = dict(good, name='b.zip', browser_download_url='https://example.com/b.zip')
    with mock.patch('urllib.request.urlopen', fake_urlopen({bad['browser_download_url']: b'tampered'})):
        with pytest.raises(ChilichipError, match='damaged'):
            firmware.download(bad, tmp_path)
    assert not (tmp_path / 'b.zip').exists()
    assert not list(tmp_path.glob('*.part'))


def test_download_uses_cache(tmp_path):
    good = asset('a.zip', b'payload')
    (tmp_path / 'a.zip').write_bytes(b'payload')
    with mock.patch('urllib.request.urlopen', side_effect=AssertionError('no download expected')):
        assert firmware.download(good, tmp_path).read_bytes() == b'payload'


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_fetch_firmware(tmp_path, test_resources):
    blit = (test_resources / 'doom-fire-vgc.blit').read_bytes()
    sdk_zip = make_zip({
        'bin/blit-loader.uf2': b'loader',
        'bin/vgc-os.blit': blit,
        'bin/vgc-os-factory.uf2': b'factory',
        'bin/other.blit': b'x',
    })
    sdk_asset = asset('32blit-sdk-v1.0.1-VGC-blit.zip', sdk_zip)
    player_asset = asset('citsy-32blit.blit', blit)
    releases = {
        firmware.SDK_REPO: {'tag_name': 'v1.0.1', 'assets': [sdk_asset]},
        firmware.PLAYER_REPO: {'tag_name': 'v0.2.0', 'assets': [player_asset]},
    }
    files = {sdk_asset['browser_download_url']: sdk_zip, player_asset['browser_download_url']: blit}

    with mock.patch.object(firmware, 'latest_release', side_effect=releases.get), \
            mock.patch('urllib.request.urlopen', fake_urlopen(files)):
        fw = firmware.fetch_firmware(tmp_path)

    assert fw.version == 'v1.0.1'
    assert fw.loader.read_bytes() == b'loader'
    assert fw.factory.read_bytes() == b'factory'
    assert fw.home.read_bytes() == blit
    assert fw.player.name == 'citsy-32blit.blit'


def test_fetch_firmware_without_player(tmp_path):
    sdk_zip = make_zip({'bin/blit-loader.uf2': b'l', 'bin/vgc-os.blit': b'h', 'bin/vgc-os-factory.uf2': b'f'})
    sdk_asset = asset('32blit-sdk-v1.0.1-VGC-blit.zip', sdk_zip)
    releases = {
        firmware.SDK_REPO: {'tag_name': 'v1.0.1', 'assets': [sdk_asset]},
        firmware.PLAYER_REPO: {'tag_name': 'v0.1.3', 'assets': [asset('citsy-32blit-v0.1.3-VGC.zip', b'')]},
    }
    log = []
    with mock.patch.object(firmware, 'latest_release', side_effect=releases.get), \
            mock.patch('urllib.request.urlopen', fake_urlopen({sdk_asset['browser_download_url']: sdk_zip})):
        fw = firmware.fetch_firmware(tmp_path, log=log.append)
    assert fw.player is None
    assert any('Bitsy player' in line for line in log)


def firmware_for(test_resources, tmp_path):
    return firmware.Firmware(
        version='v1.0.1',
        loader=tmp_path / 'blit-loader.uf2',
        home=test_resources / 'doom-fire-vgc.blit',
        factory=tmp_path / 'vgc-os-factory.uf2',
        player=None,
    )


def installed(info, checksum=None):
    return InstalledGame(block=4, size=1000, title=info.title, author=info.author,
                         version=info.version, checksum=checksum or info.checksum)


def test_plan_up_to_date(test_resources, tmp_path):
    fw = firmware_for(test_resources, tmp_path)
    info = read_blit(fw.home)
    plan = firmware.make_plan(fw, LoaderVersion('v1.0.1', (0, 6)), [installed(info)])
    assert not plan.loader
    assert plan.blits == []
    assert plan.lines == []


def test_plan_old_console(test_resources, tmp_path):
    fw = firmware_for(test_resources, tmp_path)
    info = read_blit(fw.home)
    plan = firmware.make_plan(fw, None, [installed(info, checksum=1)])
    assert plan.loader
    assert plan.blits == [fw.home]
    assert plan.lines[0] == 'Loader: unknown -> v1.0.1'


def test_plan_force(test_resources, tmp_path):
    fw = firmware_for(test_resources, tmp_path)
    info = read_blit(fw.home)
    plan = firmware.make_plan(fw, LoaderVersion('v1.0.1', (0, 6)), [installed(info)], force=True)
    assert plan.loader
    assert plan.blits == [fw.home]


def test_update_console(test_resources, tmp_path):
    fw = firmware_for(test_resources, tmp_path)
    fw.loader.write_bytes(b'loader')
    bootsel = tmp_path / 'RP2350'
    bootsel.mkdir()
    console = FakeConsole(b'32BL__OK\x04\x00')
    plan = firmware.Plan(loader=True, blits=[fw.home], lines=['x'])

    with mock.patch.object(firmware, 'reboot_to_bootsel') as reboot, \
            mock.patch.object(firmware, 'find_bootsel_drive', return_value=bootsel), \
            mock.patch.object(firmware, 'find_console', return_value='/dev/ttyACM1'), \
            mock.patch.object(firmware, 'Console', return_value=console):
        firmware.update_console(fw, plan, '/dev/ttyACM0', log=lambda *a: None)

    reboot.assert_called_once_with('/dev/ttyACM0')
    assert (bootsel / 'blit-loader.uf2').read_bytes() == b'loader'
    assert console.sent().startswith(b'32BLPROGdoom-fire-vgc.blit\x00')


def test_update_console_falls_back_to_hold_x(tmp_path, test_resources):
    fw = firmware_for(test_resources, tmp_path)
    fw.loader.write_bytes(b'loader')
    log = []
    with mock.patch.object(firmware, 'reboot_to_bootsel'), \
            mock.patch.object(firmware, 'wait_for', return_value=None):
        with pytest.raises(ChilichipError, match='RP2350'):
            firmware.update_console(fw, firmware.Plan(True, [], []), '/dev/ttyACM0', log=log.append)
    assert any('hold X' in line for line in log)
