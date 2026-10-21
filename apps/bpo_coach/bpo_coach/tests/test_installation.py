"""Run with Bench against the pinned Frappe/MariaDB stack."""
import frappe
from frappe.tests import IntegrationTestCase

from bpo_coach.api import workspace
from bpo_coach.security import insert


class TestInstallation(IntegrationTestCase):
    def test_scoped_metadata_loads_without_shadowing_framework_methods(self):
        for doctype in ('BPO Process Access', 'AI Asset', 'AI Scenario',
                        'AI Scenario Version', 'BPO Training Assignment', 'AI Attempt'):
            with self.subTest(doctype=doctype):
                meta = frappe.get_meta(doctype, cached=False)
                self.assertTrue(callable(meta.process))
                self.assertTrue(meta.has_field('bpo_process'))
                self.assertFalse(meta.has_field('process'))

    def test_roles_and_native_fields_are_installed(self):
        for role in ('BPO Administrator', 'BPO Trainer', 'BPO Learner'):
            self.assertTrue(frappe.db.exists('Role', role))
        self.assertTrue(frappe.get_meta('LMS Course').has_field('bpo_process'))
        self.assertTrue(frappe.get_meta('LMS Batch').has_field('bpo_process'))
        self.assertTrue(frappe.db.get_global('bpo_coach_setup_complete'))
        settings = frappe.get_single('LMS Settings')
        self.assertTrue(settings.disable_signup)
        self.assertFalse(settings.allow_guest_access)
        self.assertTrue(settings.persona_captured)

    def test_process_storage_preserves_workspace_response_contract(self):
        previous_user = frappe.session.user
        frappe.set_user('Administrator')
        try:
            client = insert('BPO Client', title='Integration scope client', enabled=1)
            process = insert('BPO Process', title='Integration scope process', client=client.name, enabled=1)
            access = insert('BPO Process Access', member='Administrator', bpo_process=process.name)
            self.assertEqual(access.access_key, 'Administrator|' + process.name)
            scenario = insert('AI Scenario', title='Integration scenario', bpo_process=process.name,
                              company_wide=0, draft_json='{}', draft_revision=1)
            result = next(row for row in workspace()['scenarios'] if row.name == scenario.name)
            self.assertEqual(result.process, process.name)
            self.assertNotIn('bpo_process', result)
        finally:
            frappe.set_user(previous_user)
