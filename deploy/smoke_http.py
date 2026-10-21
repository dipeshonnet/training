"""Check disposable CI file probes through the actual Nginx/Frappe boundary."""
from http.cookiejar import CookieJar
import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request


def check():
    host = os.environ['SITE_HOSTNAME']
    base = os.environ.get('SMOKE_ORIGIN', 'http://127.0.0.1:8080')
    guest = build_opener()
    authenticated = build_opener(HTTPCookieProcessor(CookieJar()))
    private_file = os.environ['PRIVATE_PROBE_URL']
    public_file = os.environ['PUBLIC_PROBE_URL']
    assert private_file.startswith('/private/files/') and public_file.startswith('/files/')

    def request(opener, path, data=None):
        req = Request(base + path, data=data, headers={'Host': host})
        try:
            with opener.open(req, timeout=20) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    status, _ = request(guest, private_file)
    assert status == 403, f'Guest private-file response: {status}'
    status, body = request(guest, public_file)
    assert (status, body) == (200, b'ci-public-probe'), f'Public file failed: {status}'
    credentials = urlencode({'usr': 'Administrator', 'pwd': os.environ['ADMIN_PASSWORD']}).encode()
    status, _ = request(authenticated, '/api/method/login', credentials)
    assert status == 200, f'Login failed: {status}'
    status, body = request(authenticated, '/api/method/frappe.auth.get_logged_user')
    assert status == 200 and json.loads(body).get('message') == 'Administrator', f'Session failed: {status}'
    status, body = request(authenticated, private_file)
    assert (status, body) == (200, b'ci-private-probe'), f'Authenticated private file failed: {status}'
    status, _ = request(authenticated, '/protected' + private_file)
    assert status == 404, f'Internal Nginx route was accessible: {status}'
    status, body = request(authenticated, '/coach')
    assert status == 200 and b'ai-coach' in body, f'Portal failed: {status}'
    print('Nginx public/private files, login and authenticated portal checks passed.')


if __name__ == '__main__':
    check()
