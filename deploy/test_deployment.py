"""Offline deployment contract checks; these do not replace a live Bench run."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from apply_bridge import apply
from entrypoint import initialize, main
from materialize_assets import materialize

REPO = Path(__file__).resolve().parents[1]
PIN = json.loads((REPO / 'deploy/versions.json').read_text())['applications']['lms']['commit']


class BridgePatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = json.loads((REPO / 'deploy/patches/lms-ai-coach.json').read_text())
        for name in manifest:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(['git', 'show', f'{PIN}:{name}'], cwd=REPO))
        shutil.copytree(REPO / 'deploy/patches', self.root / 'deploy/patches')
        target = self.root / 'apps/bpo_coach/frontend/src'
        target.mkdir(parents=True)
        shutil.copyfile(REPO / 'apps/bpo_coach/frontend/src/bridge.js', target / 'bridge.js')

    def test_applies_to_pin_and_is_repeatable(self):
        apply(self.root)
        apply(self.root)
        source = (self.root / 'frontend/src/utils/index.js').read_text()
        self.assertEqual(source.count('ai_coach: AICoach'), 1)
        self.assertIn("to: 'AICoach'", source)
        self.assertIn("window.location.assign('/coach')", (self.root / 'frontend/src/routes.js').read_text())
        self.assertIn("'AI Coach'", (self.root / 'frontend/src/utils/mobileNav.ts').read_text())
        self.assertEqual((self.root / 'frontend/src/utils/aiCoach.js').read_bytes(),
                         (REPO / 'apps/bpo_coach/frontend/src/bridge.js').read_bytes())

    def test_rejects_drift_before_changing_any_sources(self):
        source = self.root / 'frontend/src/routes.js'
        source.write_text(source.read_text() + '\n// upstream change\n')
        with self.assertRaisesRegex(RuntimeError, 'source changed'):
            apply(self.root)
        self.assertNotIn('ai_coach: AICoach', (self.root / 'frontend/src/utils/index.js').read_text())

    def test_rejects_partial_patch(self):
        apply(self.root)
        name = 'frontend/src/routes.js'
        (self.root / name).write_bytes(subprocess.check_output(['git', 'show', f'{PIN}:{name}'], cwd=REPO))
        with self.assertRaisesRegex(RuntimeError, 'partially applied'):
            apply(self.root)


class Bootstrap(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sites').mkdir()
        self.assets = self.root / 'built'
        self.assets.mkdir()
        (self.assets / 'main.js').write_text('asset')
        self.site = 'training.everydayai.work'
        self.env = dict(DB_ROOT_PASSWORD='test-only-db', ADMIN_PASSWORD='test-only-admin')

    def existing_site(self):
        site = self.root / 'sites' / self.site
        site.mkdir()
        (site / 'site_config.json').write_text('{"encryption_key":"test-only"}')

    def test_new_site_installs_in_order_then_migrates(self):
        with patch('entrypoint.run') as run:
            initialize(self.root, self.site, self.assets, self.env)
        calls = [call.args for call in run.call_args_list]
        self.assertEqual(calls[0][:3], ('bench', 'new-site', self.site))
        self.assertEqual([args[-1] for args in calls[1:4]], ['payments', 'lms', 'bpo_coach'])
        self.assertEqual(calls[4][-1], 'migrate')
        self.assertEqual(calls[-1][-1], 'enable-scheduler')

    def test_existing_site_resumes_and_preserves_configuration(self):
        self.existing_site()
        config = self.root / 'sites/common_site_config.json'
        config.write_text('{"custom_setting":true}')
        with patch('entrypoint.run') as run:
            initialize(self.root, self.site, self.assets, {})
        self.assertFalse(any('new-site' in call.args for call in run.call_args_list))
        self.assertEqual(run.call_args_list[0].args[-2:], ('install-app', 'payments'))
        self.assertTrue(json.loads(config.read_text())['custom_setting'])
        self.assertEqual(json.loads((self.root / 'sites' / self.site / 'site_config.json').read_text())['encryption_key'], 'test-only')
        self.assertEqual((self.root / 'sites/assets/main.js').read_text(), 'asset')

    def test_failed_install_blocks_migration_and_scheduler(self):
        self.existing_site()
        with patch('entrypoint.run', side_effect=[None, RuntimeError('install failed')]) as run:
            with self.assertRaisesRegex(RuntimeError, 'install failed'):
                initialize(self.root, self.site, self.assets, {})
        self.assertEqual(len(run.call_args_list), 2)

    def test_web_and_explicit_commands_do_not_initialize(self):
        for argv, executable in [(['entrypoint.py', 'web'], 'env/bin/gunicorn'),
                                 (['entrypoint.py', 'bench', '--site', self.site, 'list-apps'], 'bench')]:
            with patch('entrypoint.sys.argv', argv), patch('entrypoint.os.chdir'), patch('entrypoint.initialize') as init, patch('entrypoint.os.execvp') as execute:
                main()
            init.assert_not_called()
            self.assertEqual(execute.call_args.args[0], executable)


class Assets(unittest.TestCase):
    def test_materializes_app_public_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'app/public'
            public.mkdir(parents=True)
            (public / 'main.js').write_text('app bundle')
            assets = root / 'assets'
            assets.mkdir()
            try:
                (assets / 'lms').symlink_to(public, target_is_directory=True)
                (public / 'alias.js').symlink_to(public / 'main.js')
            except OSError as error:
                self.skipTest(f'Symlink creation unavailable: {error}')
            materialize(assets, root / 'export')
            shutil.rmtree(root / 'app')
            self.assertEqual((root / 'export/lms/main.js').read_text(), 'app bundle')
            self.assertEqual((root / 'export/lms/alias.js').read_text(), 'app bundle')
            self.assertFalse(any(path.is_symlink() for path in (root / 'export').rglob('*')))


if __name__ == '__main__':
    unittest.main()
