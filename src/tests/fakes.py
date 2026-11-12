import io

from chilichip.console import Console


class FakeConsole(Console):
    """Console that talks to BytesIO buffers instead of a serial port."""
    timeout = 5
    port = '_fakeconsole_'

    def __init__(self, reply=b''):
        self._reader = io.BytesIO(reply)
        self._writer = io.BytesIO()

    def read(self, n=1):
        return self._reader.read(n)

    def write(self, b):
        return self._writer.write(b)

    def sent(self):
        return self._writer.getvalue()

    @property
    def in_waiting(self):
        return 0

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Comport:
    def __init__(self, vid, pid, device):
        self.vid = vid
        self.pid = pid
        self.device = device


class FakePlatform:
    """In-memory copy of chili-platform's device API, served over real HTTP on localhost.

    Shapes and errors follow chili-platform docs/openapi.yaml and src/devices/views.py:
    POST /api/devices/authorize/, POST /api/devices/token/ (RFC 8628),
    GET /api/device/library/ and GET /api/device/games/<id>.<ext> with "Authorization: Device <token>".
    """

    def __init__(self, games=None, polls_before_approval=1, outcome='approve'):
        import hashlib
        self.games = {}  # id -> (row, bytes)
        for game in games or []:
            data = game['data']
            row = {
                'id': game['id'], 'title': game['title'], 'author': game.get('author', 'ada'),
                'updated_at': '2026-11-11T10:00:00Z', 'size': len(data),
                'sha256': game.get('sha256', hashlib.sha256(data).hexdigest()),
                'engine': game.get('engine', 'bitsy'),
                'download_url': f"/api/device/games/{game['id']}{game.get('extension', '.bitsy')}",
            }
            self.games[game['id']] = (row, data)
        self.polls_before_approval = polls_before_approval
        self.outcome = outcome  # approve, deny, expire, slow_down
        self.token = 'device-token-123'
        self.revoked = False
        self.name = None
        self.requests = []  # (method, path, headers, json body)
        self.server = None

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_address[1]}'

    def __enter__(self):
        import http.server
        import json
        import threading

        platform = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, body=None, raw=None, content_type='application/json'):
                data = raw if raw is not None else json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def authorized(self):
                if self.headers.get('Authorization') != f'Device {platform.token}' or platform.revoked:
                    self.reply(401, {'detail': 'Unknown or revoked device token.'})
                    return False
                return True

            def do_POST(self):
                length = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(length) or b'{}')
                platform.requests.append(('POST', self.path, dict(self.headers), body))
                if self.path == '/api/devices/authorize/':
                    platform.name = body.get('name') or 'ChiliChip'
                    self.reply(200, {
                        'device_code': 'secret-device-code', 'user_code': 'BCDF-GHJK',
                        'verification_uri': 'https://platform.example/link',
                        'verification_uri_complete': 'https://platform.example/link?code=BCDF-GHJK',
                        'expires_in': 900, 'interval': 5,
                    })
                elif self.path == '/api/devices/token/':
                    if body.get('grant_type') != 'urn:ietf:params:oauth:grant-type:device_code':
                        self.reply(400, {'error': 'unsupported_grant_type'})
                    elif body.get('device_code') != 'secret-device-code':
                        self.reply(400, {'error': 'invalid_grant'})
                    elif platform.polls_before_approval > 0:
                        platform.polls_before_approval -= 1
                        error = 'slow_down' if platform.outcome == 'slow_down' else 'authorization_pending'
                        self.reply(400, {'error': error})
                    elif platform.outcome == 'deny':
                        self.reply(400, {'error': 'access_denied'})
                    elif platform.outcome == 'expire':
                        self.reply(400, {'error': 'expired_token'})
                    else:
                        self.reply(200, {'access_token': platform.token, 'token_type': 'Device',
                                         'device': {'id': 7, 'name': platform.name}})
                else:
                    self.reply(404, {'detail': 'Not found.'})

            def do_GET(self):
                platform.requests.append(('GET', self.path, dict(self.headers), None))
                if self.path == '/api/device/library/':
                    if self.authorized():
                        self.reply(200, {'games': [row for row, _ in platform.games.values()]})
                    return
                for row, data in platform.games.values():
                    if self.path == row['download_url']:
                        if self.authorized():
                            self.reply(200, raw=data, content_type='text/plain; charset=utf-8')
                        return
                self.reply(404, {'detail': 'Not found.'})

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
