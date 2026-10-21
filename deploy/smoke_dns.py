"""Verify Nginx recovery when Compose replaces the backend at a different IP.

Run only on a disposable verification stack: this recreates its backend service,
preserving the named database and site volumes.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

COMPOSE = ['docker', 'compose', '-f', 'deploy/compose.yaml']


def capture(*command):
    return subprocess.check_output(command, text=True).strip()


def backend_address():
    container = capture(*COMPOSE, 'ps', '-q', 'backend')
    details = json.loads(capture('docker', 'inspect', container))[0]
    networks = details['NetworkSettings']['Networks']
    if len(networks) != 1:
        raise RuntimeError('The DNS probe requires one Compose application network.')
    network, endpoint = next(iter(networks.items()))
    return network, endpoint['IPAddress']


def wait_for_recovery(origin, host):
    # Existing Nginx workers can briefly retain both replica addresses. Require
    # sustained success across a DNS refresh before exercising session controls.
    deadline = time.monotonic() + 60
    stable_since = None
    request = Request(origin + '/api/method/ping', headers={'Host': host})
    while time.monotonic() < deadline:
        try:
            with urlopen(request, timeout=3) as response:
                assert response.status == 200 and json.load(response)['message'] == 'pong'
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= 5:
                return
        except HTTPError as error:
            if error.code not in (502, 503, 504):
                raise
            stable_since = None
        except (URLError, TimeoutError, ConnectionError):
            stable_since = None
        time.sleep(1)
    raise AssertionError('Nginx did not sustain backend recovery within 60 seconds.')


def check():
    network, old_address = backend_address()
    old_container = capture(*COMPOSE, 'ps', '-q', 'backend')
    # Start the replacement while the original still owns its address. This
    # forces a different dynamic IP without requiring a fixed IPAM subnet.
    try:
        subprocess.run(COMPOSE + ['up', '--no-build', '--no-deps', '-d', '--wait',
                                   '--wait-timeout', '180', '--scale', 'backend=2', 'backend'], check=True)
        subprocess.run(['docker', 'rm', '--force', old_container], check=True)
        subprocess.run(COMPOSE + ['up', '--no-build', '--no-deps', '-d', '--wait',
                                   '--wait-timeout', '180', 'backend', 'frontend'], check=True)
        _, new_address = backend_address()
        assert new_address != old_address, 'The backend address did not change.'
        origin = os.environ.get('SMOKE_ORIGIN', 'http://127.0.0.1:8080')
        wait_for_recovery(origin, os.environ['SITE_HOSTNAME'])
        subprocess.run([sys.executable, str(Path(__file__).with_name('smoke_http.py'))], check=True)
        print(f'Nginx recovered after backend address changed from {old_address} to {new_address}.')
    finally:
        # Also restore service availability when an assertion or setup fails.
        subprocess.run(COMPOSE + ['up', '--no-build', '--no-deps', '-d', '--scale', 'backend=1',
                                  'backend', 'frontend'],
                        check=False)


if __name__ == '__main__':
    check()
