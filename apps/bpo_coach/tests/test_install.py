"""Install ordering and interrupted-defaults recovery without a live Frappe DB."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch


class InstallRecovery(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        field_module = MagicMock()
        modules = {'frappe': self.frappe,
                   'frappe.custom': MagicMock(), 'frappe.custom.doctype': MagicMock(),
                   'frappe.custom.doctype.custom_field': MagicMock(),
                   'frappe.custom.doctype.custom_field.custom_field': field_module}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('install_under_test', Path(__file__).parents[1] / 'bpo_coach/install.py')
            self.install = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.install)

    def test_roles_exist_before_custom_fields_are_synced(self):
        with patch.object(self.install, 'ensure_roles') as roles, patch.object(self.install, 'create_custom_fields') as fields, patch.object(self.install, 'setup_defaults') as defaults:
            sequence = MagicMock()
            sequence.attach_mock(roles, 'roles')
            sequence.attach_mock(fields, 'fields')
            sequence.attach_mock(defaults, 'defaults')
            self.install.after_migrate()
        self.assertEqual([call[0] for call in sequence.mock_calls], ['roles', 'fields', 'defaults'])

    def test_migrate_finishes_defaults_after_interrupted_install(self):
        self.frappe.db.get_global.return_value = None
        self.install.after_migrate()
        self.frappe.get_doc.assert_called_with('User', 'Administrator')
        self.frappe.db.set_global.assert_called_once_with('bpo_coach_setup_complete', '1')

    def test_completed_setup_preserves_administrator_settings(self):
        self.frappe.db.get_global.return_value = '1'
        self.install.setup_defaults()
        self.frappe.get_single.assert_not_called()
        self.frappe.db.set_global.assert_not_called()

    def test_failed_defaults_are_not_marked_complete(self):
        self.frappe.db.get_global.return_value = None
        self.frappe.get_single.side_effect = RuntimeError('interrupted')
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            self.install.setup_defaults()
        self.frappe.db.set_global.assert_not_called()
