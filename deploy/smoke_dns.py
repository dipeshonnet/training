"""Verify Nginx recovery when Compose replaces the backend at a different IP.

Run only on a disposable verification stack: this recreates its backend service,
preserving the named database and site volumes.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen
import uuid

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


def check():
    network, old_address = backend_address()
    config = json.loads(capture(*COMPOSE, 'config', '--format', 'json'))
    holder = 'ai-coach-dns-probe-' + uuid.uuid4().hex[:10]
    # Hold the old address so the new backend must receive a different one.
    # Without this, Docker can reuse it and a stale Nginx resolver appears valid.
    subprocess.run(COMPOSE + ['rm', '--stop', '--force', 'backend'], check=True)
    try:
        capture('docker', 'run', '--detach', '--rm', '--name', holder, '--network', network,
                '--ip', old_address, config['services']['redis-cache']['image'], 'sleep', '300')
        subprocess.run(COMPOSE + ['up', '--no-build', '--no-deps', '-d', '--wait',
                                   '--wait-timeout', '180', 'backend', 'frontend'], check=True)
        _, new_address = backend_address()
        assert new_address != old_address, 'The backend address did not change.'
        origin = os.environ.get('SMOKE_ORIGIN', 'http://127.0.0.1:8080')
        request = Request(origin + '/api/method/ping', headers={'Host': os.environ['SITE_HOSTNAME']})
        with urlopen(request, timeout=20) as response:
            assert response.status == 200 and json.load(response)['message'] == 'pong'
        subprocess.run([sys.executable, str(Path(__file__).with_name('smoke_http.py'))], check=True)
        print(f'Nginx recovered after backend address changed from {old_address} to {new_address}.')
    finally:
        subprocess.run(['docker', 'rm', '--force', holder], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, check=False)
        # Also restore service availability when an assertion or setup fails.
        subprocess.run(COMPOSE + ['up', '--no-build', '--no-deps', '-d', 'backend', 'frontend'],
                        check=False)


if __name__ == '__main__':
    check()
