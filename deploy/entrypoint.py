"""One image, explicit process roles; never initialize or migrate on web startup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path('/home/frappe/frappe-bench')
os.chdir(ROOT)
site = os.environ['SITE_HOSTNAME']

def run(*args):
    subprocess.run(args, check=True)

role = sys.argv[1] if len(sys.argv) > 1 else 'web'
if role == 'initialize':
    config = {'db_host': 'db', 'db_port': 3306, 'redis_cache': 'redis://redis-cache:6379',
              'redis_queue': 'redis://redis-queue:6379', 'redis_socketio': 'redis://redis-queue:6379',
              'socketio_port': 9000, 'default_site': site, 'serve_default_site': True}
    (ROOT / 'sites/common_site_config.json').write_text(json.dumps(config))
    (ROOT / 'sites/apps.txt').write_text('frappe\npayments\nlms\nbpo_coach\n')
    shutil.copytree('/home/frappe/assets-built', ROOT / 'sites/assets', dirs_exist_ok=True, symlinks=True)
    if not (ROOT / 'sites' / site / 'site_config.json').exists():
        run('bench', 'new-site', site, '--db-host', 'db', '--db-root-password', os.environ['DB_ROOT_PASSWORD'],
            '--admin-password', os.environ['ADMIN_PASSWORD'], '--mariadb-user-host-login-scope', '%')
        for app in ('payments', 'lms', 'bpo_coach'):
            run('bench', '--site', site, 'install-app', app)
        run('bench', '--site', site, 'set-config', 'host_name', 'https://' + site)
        run('bench', '--site', site, 'enable-scheduler')
    sys.exit(0)
commands = {
    'web': ['env/bin/gunicorn', '--bind', '0.0.0.0:8000', '--workers', '2', '--timeout', '120', 'frappe.app:application'],
    'worker': ['bench', 'worker', '--queue', 'short,default,long'],
    'scheduler': ['bench', 'schedule'],
    'websocket': ['node', 'apps/frappe/socketio.js'],
}
command = commands.get(role, sys.argv[1:])
os.execvp(command[0], command)
