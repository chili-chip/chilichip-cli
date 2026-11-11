"""Link this computer to a Chili Platform account and get games from its library.

Linking follows the OAuth 2.0 Device Authorization Grant (RFC 8628,
https://www.rfc-editor.org/rfc/rfc8628), the same flow chili-platform serves for
consoles: we ask for a code, the person enters it at /link on the website, and
we poll until we get a device token. The token only works on the device API:
the library list and game downloads.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import socket
import time
import urllib.error
import urllib.request

import click

from . import ChilichipError

DEFAULT_URL = 'https://platform.chilichip.eu'
DEVICE_GRANT = 'urn:ietf:params:oauth:grant-type:device_code'
NAME_LENGTH = 60  # the platform keeps the first 60 characters
# engines the console can play, and how the CLI installs them
CONSOLE_ENGINES = {'bitsy': 'Bitsy', 'blit': 'ChiliChip'}
ENGINE_NAMES = {'bitsy': 'Bitsy', 'beat': 'Chili Beat', 'blit': 'ChiliChip'}


class PlatformError(ChilichipError):
    pass


def platform_url(url):
    return (url or DEFAULT_URL).rstrip('/')


def config_dir():
    return pathlib.Path(click.get_app_dir('chilichip'))


def cache_dir():
    return config_dir() / 'cache' / 'platform'


def credentials_path():
    return config_dir() / 'platform.json'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def default_name():
    return f'chilichip CLI on {socket.gethostname()}'[:NAME_LENGTH]


# saved tokens, one per platform URL, readable only by this user

def _read_credentials():
    try:
        return json.loads(credentials_path().read_text())
    except (OSError, ValueError):
        return {}


def _write_credentials(data):
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # create it as 0600 so the token is never readable by others, not even for a moment
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=2)
    if os.name == 'posix':
        os.chmod(path, 0o600)


def save_token(url, token, device):
    data = _read_credentials()
    data[url] = {'token': token, 'device': device}
    _write_credentials(data)


def load_token(url):
    entry = _read_credentials().get(url)
    return entry['token'] if entry else None


def forget_token(url):
    data = _read_credentials()
    if data.pop(url, None) is None:
        return False
    _write_credentials(data)
    return True


class Platform:
    """A small client for the platform's device API."""

    def __init__(self, url, token=None):
        self.url = platform_url(url)
        self.token = token

    def request(self, method, path, body=None):
        """Send a request. Returns (status, headers, bytes); 4xx answers are returned, not raised."""
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, method=method)
        request.add_header('Accept', 'application/json')
        request.add_header('User-Agent', 'chilichip-cli')
        if data is not None:
            request.add_header('Content-Type', 'application/json')
        if self.token:
            request.add_header('Authorization', f'Device {self.token}')
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as e:
            if e.code == 401 and self.token:
                raise PlatformError(
                    'The platform no longer knows this computer: it was unlinked or revoked. '
                    'Run: chilichip login')
            if 400 <= e.code < 500:
                return e.code, e.headers, e.read()
            raise PlatformError(f'The platform answered {e.code} for {path}. Try again later.')
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, 'reason', e)
            raise PlatformError(f'Cannot reach {self.url}: {reason}')

    def json(self, method, path, body=None):
        status, _, data = self.request(method, path, body)
        try:
            return status, json.loads(data or b'{}')
        except ValueError:
            raise PlatformError(f'Unexpected answer from {self.url}{path} (status {status}).')

    # RFC 8628

    def authorize(self, name):
        status, body = self.json('POST', '/api/devices/authorize/', {'name': name[:NAME_LENGTH]})
        if status != 200:
            raise PlatformError(f'The platform refused to start linking ({status}). Try again in a minute.')
        return body

    def wait_for_token(self, authorization, stop=None):
        """Poll until the person approves or denies the code (RFC 8628 3.4 and 3.5).

        stop is an optional threading.Event that ends the wait early, for the TUI.
        """
        interval = int(authorization.get('interval') or 5)
        deadline = time.monotonic() + int(authorization.get('expires_in') or 900)
        body = {'grant_type': DEVICE_GRANT, 'device_code': authorization['device_code']}
        while True:
            if time.monotonic() >= deadline:
                raise PlatformError('The code expired before it was entered. Run chilichip login again.')
            if stop is None:
                time.sleep(interval)
            elif stop.wait(interval):
                raise PlatformError('Linking was cancelled.')
            status, answer = self.json('POST', '/api/devices/token/', body)
            if status == 200:
                return answer
            error = answer.get('error')
            if error == 'authorization_pending':
                continue
            if error == 'slow_down':
                interval += 5
                continue
            if error == 'access_denied':
                raise PlatformError('Linking was denied on the website.')
            if error == 'expired_token':
                raise PlatformError('The code expired before it was entered. Run chilichip login again.')
            raise PlatformError(f'Linking failed: {error or status}.')

    # device API

    def library(self):
        if not self.token:
            raise PlatformError(f'This computer is not linked to {self.url}. Run: chilichip login')
        status, body = self.json('GET', '/api/device/library/')
        if status != 200:
            raise PlatformError(f'Cannot read the library ({status}).')
        return body.get('games', [])

    def download(self, game, folder=None):
        """Download a game into the cache and check its sha256. Reuses a good copy."""
        folder = pathlib.Path(folder or cache_dir())
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / local_name(game)
        if path.exists() and sha256(path.read_bytes()) == game['sha256']:
            return path
        status, _, data = self.request('GET', game['download_url'])
        if status != 200:
            raise PlatformError(f'Cannot download {game["title"]} ({status}).')
        if sha256(data) != game['sha256']:
            raise PlatformError(f'The download of {game["title"]} has the wrong checksum. Try again.')
        path.write_bytes(data)
        return path


def local_name(game):
    """A safe file name from the title, with the extension of the download."""
    extension = pathlib.PurePosixPath(game['download_url']).suffix
    slug = re.sub(r'[^a-z0-9]+', '-', game['title'].lower()).strip('-')
    return f'{slug or "game-" + str(game["id"])}{extension}'


def console_can_play(game):
    return game.get('engine', 'bitsy') in CONSOLE_ENGINES


def pick_games(games, names):
    """Games matching each name (title, any case) or id, in the order given."""
    picked = []
    for name in names:
        match = next((g for g in games if g['title'].lower() == name.lower() or str(g['id']) == name), None)
        if match is None:
            raise PlatformError(f'No game called "{name}" in your library. See: chilichip library')
        picked.append(match)
    return picked


def login(url, name, echo=click.echo, stop=None):
    """Link this computer: show the code, wait for the person, save the token."""
    client = Platform(url)
    authorization = client.authorize(name)
    echo(f'On any device, open {authorization["verification_uri"]}')
    echo(f'and enter the code: {authorization["user_code"]}')
    echo(f'Or open: {authorization["verification_uri_complete"]}')
    echo('Waiting for you to approve it...')
    answer = client.wait_for_token(authorization, stop)
    device = answer.get('device') or {}
    save_token(client.url, answer['access_token'], device)
    return device


def size_text(size):
    return f'{size} B' if size < 1024 else f'{size / 1024:.0f} KB'
