"""One image, explicit process roles; never initialize or migrate on web startup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path('/home/frappe/frappe-bench')
APPS = ('payments', 'lms', 'bpo_coach')

def run(*args):
    subprocess.run(args, check=True)

def initialize(root, site, assets, environ):
    config = {'db_host': 'db', 'db_port': 3306, 'redis_cache': 'redis://redis-cache:6379',
              'redis_queue': 'redis://redis-queue:6379', 'redis_socketio': 'redis://redis-queue:6379',
              'socketio_port': 9000, 'default_site': site, 'serve_default_site': True}
    config_path = root / 'sites/common_site_config.json'
    existing = json.loads(config_path.read_text()) if config_path.exists() else {}
    existing.update(config)
    config_path.write_text(json.dumps(existing))
    (root / 'sites/apps.txt').write_text('frappe\npayments\nlms\nbpo_coach\n')
    shutil.copytree(assets, root / 'sites/assets', dirs_exist_ok=True, symlinks=False)
    if not (root / 'sites' / site / 'site_config.json').exists():
        run('bench', 'new-site', site, '--db-host', 'db', '--db-root-password', environ['DB_ROOT_PASSWORD'],
            '--admin-password', environ['ADMIN_PASSWORD'], '--mariadb-user-host-login-scope', '%')
    # Frappe skips installed apps. A retry must resume app installation even
    # when a previous failed setup already wrote site_config.json.
    for app in APPS:
        run('bench', '--site', site, 'install-app', app)
    run('bench', '--site', site, 'migrate')
    run('bench', '--site', site, 'set-config', 'host_name', 'https://' + site)
    run('bench', '--site', site, 'enable-scheduler')


def main():
    os.chdir(ROOT)
    role = sys.argv[1] if len(sys.argv) > 1 else 'web'
    if role == 'initialize':
        initialize(ROOT, os.environ['SITE_HOSTNAME'], Path('/home/frappe/assets-built'), os.environ)
        return
    commands = {
        'web': ['env/bin/gunicorn', '--chdir', 'sites', '--bind', '0.0.0.0:8000', '--workers', '2', '--timeout', '120', 'frappe.app:application'],
        'worker': ['bench', 'worker', '--queue', 'short,default,long'],
        'scheduler': ['bench', 'schedule'],
        'websocket': ['node', 'apps/frappe/socketio.js'],
    }
    command = commands.get(role, sys.argv[1:])
    os.execvp(command[0], command)


if __name__ == '__main__':
    main()
