"""Exercise real Socket.IO authentication through the same Nginx origin."""
from http.cookiejar import CookieJar
import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request


def check():
    host = os.environ['SITE_HOSTNAME']
    base = os.environ.get('SMOKE_ORIGIN', 'http://127.0.0.1:8080')
    origin = os.environ.get('SOCKET_ORIGIN', 'http://' + host + ':8080')
    authenticated = build_opener(HTTPCookieProcessor(CookieJar()))
    guest = build_opener()

    def request(opener, path, data=None, browser_origin=None):
        headers = {'Host': host}
        if browser_origin:
            headers['Origin'] = browser_origin
        if data is not None:
            headers['Content-Type'] = 'text/plain;charset=UTF-8'
        try:
            with opener.open(Request(base + path, data=data, headers=headers), timeout=20) as response:
                return response.status, response.read().decode('utf-8')
        except HTTPError as error:
            return error.code, error.read().decode('utf-8')

    credentials = urlencode({'usr': 'Administrator', 'pwd': os.environ['ADMIN_PASSWORD']}).encode()
    # Login uses the normal form content type.
    with authenticated.open(Request(base + '/api/method/login', data=credentials,
                                     headers={'Host': host}), timeout=20) as response:
        assert response.status == 200, 'Realtime probe login failed'

    def connect(opener, browser_origin, expected):
        path = '/socket.io/?EIO=4&transport=polling'
        status, body = request(opener, path, browser_origin=browser_origin)
        if status != 200:
            assert not expected and status in (400, 403), f'Unexpected handshake status: {status}'
            return
        assert body.startswith('0'), 'Missing Engine.IO handshake'
        path += '&' + urlencode({'sid': json.loads(body[1:])['sid']})
        try:
            status, _ = request(opener, path, ('40/' + host + ',').encode(), browser_origin)
            assert status == 200, f'Namespace request failed: {status}'
            for _ in range(4):
                status, body = request(opener, path, browser_origin=browser_origin)
                assert status == 200, f'Namespace polling failed: {status}'
                for packet in body.split('\x1e'):
                    if packet.startswith('40/' + host + ','):
                        assert expected, 'Unauthorized socket connection was accepted'
                        return
                    if packet.startswith('44/' + host + ','):
                        assert not expected, 'Authenticated namespace connection was rejected'
                        return
                    if packet == '2':
                        request(opener, path, b'3', browser_origin)
            raise AssertionError('No Socket.IO namespace response')
        finally:
            request(opener, path, b'1', browser_origin)

    connect(authenticated, origin, True)
    connect(authenticated, None, True)
    connect(authenticated, 'https://untrusted.example', False)
    connect(guest, origin, False)
    print('Same-origin Socket.IO authentication passed; invalid origins and guests were denied.')


if __name__ == '__main__':
    check()
