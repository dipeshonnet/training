"""CSV provisioning through real User, enrollment, role and transaction hooks."""
import frappe
import inspect
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate
from werkzeug.wrappers import Request

from bpo_coach.people_import import import_people
from bpo_coach.security import insert


class TestPeopleImport(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        previous_user = frappe.session.user
        previous_request = getattr(frappe.local, 'request', None)
        self.addCleanup(frappe.set_user, previous_user)
        self.addCleanup(setattr, frappe.local, 'request', previous_request)
        frappe.set_user('Administrator')
        frappe.local.request = Request.from_values(method='POST')
        self.suffix = frappe.generate_hash(length=10)
        self.trainer = self.user('trainer', ['BPO Trainer', 'Course Creator'])
        self.learner = self.user('learner', ['BPO Learner', 'LMS Student'])
        self.client = insert('BPO Client', title='CSV client ' + self.suffix, enabled=1)
        self.process = insert('BPO Process', title='CSV process ' + self.suffix, client=self.client.name, enabled=1)
        self.other = insert('BPO Process', title='Other CSV process ' + self.suffix, client=self.client.name, enabled=1)
        insert('BPO Process Access', member=self.trainer.name, bpo_process=self.process.name)
        self.batch = self.make_batch(self.process.name, 'Accessible')
        self.other_batch = self.make_batch(self.other.name, 'Other')
        frappe.get_doc(dict(doctype='LMS Batch Enrollment', batch=self.batch.name, member=self.learner.name)).insert(ignore_permissions=True)

    def user(self, label, roles):
        user = frappe.get_doc(dict(doctype='User', email=f'csv-{label}-{self.suffix}@example.test',
            first_name='CSV ' + label, enabled=1, send_welcome_email=0, user_type='Website User',
            roles=[{'role': role} for role in roles])).insert(ignore_permissions=True)
        return user

    def make_batch(self, process, label):
        return frappe.get_doc(dict(doctype='LMS Batch', title=label + ' CSV ' + self.suffix,
            description='CSV import test batch', batch_details='CSV import integration fixture',
            bpo_process=process, start_date=nowdate(), end_date=add_days(nowdate(), 10),
            start_time='09:00:00', end_time='17:00:00', timezone='Asia/Kolkata',
            seat_count=100, instructors=[{'instructor': self.trainer.name}])).insert(ignore_permissions=True)

    def run_import(self, csv):
        # Rate limiting is exercised by HTTP; direct calls here exercise domain behavior.
        return inspect.unwrap(import_people)(csv)

    def test_admin_creates_and_updates_by_email(self):
        email = f'csv-new-{self.suffix}@example.test'
        result = self.run_import(f'name,email,password,role\nNew Person,{email},N7!csvExamplePassword123,trainer\nChanged Name,{self.learner.name.upper()},,')
        self.assertEqual(result, {'created': 1, 'updated': 1, 'errors': []})
        self.assertIn('BPO Trainer', frappe.get_roles(email))
        self.assertEqual(frappe.db.get_value('User', self.learner.name, 'full_name'), 'Changed Name')

    def test_trainer_creates_learner_and_adds_batch_idempotently(self):
        frappe.set_user(self.trainer.name)
        email = f'csv-new-{self.suffix}@example.test'
        result = self.run_import(f'name,email,password,role,batchIds\nNew Learner,{email},N7!csvExamplePassword123,learner,{self.batch.name}\nChanged,{self.learner.name},,,{self.batch.name}')
        self.assertEqual(result, {'created': 1, 'updated': 1, 'errors': []})
        self.assertEqual(frappe.db.count('LMS Batch Enrollment', {'batch': self.batch.name, 'member': self.learner.name}), 1)

    def test_trainer_cannot_escalate_or_access_other_processes(self):
        frappe.set_user(self.trainer.name)
        result = self.run_import(f'name,email,password,role,batchIds\nPromoted,{self.learner.name},,admin,\nNew Person,new-{self.suffix}@example.test,N7!csvExamplePassword123,learner,{self.other_batch.name}\nTrainer,{self.trainer.name},,learner,')
        self.assertEqual((result['created'], result['updated'], len(result['errors'])), (0, 0, 3))
        self.assertNotIn('BPO Administrator', frappe.get_roles(self.learner.name))

    def test_shared_and_privileged_accounts_are_denied_to_trainers(self):
        frappe.get_doc(dict(doctype='LMS Batch Enrollment', batch=self.other_batch.name, member=self.learner.name)).insert(ignore_permissions=True)
        frappe.set_user(self.trainer.name)
        result = self.run_import(f'name,email\nChanged,{self.learner.name}')
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(result['updated'], 0)

    def test_trainer_cannot_modify_a_privileged_learner(self):
        self.learner.add_roles('System Manager')
        frappe.set_user(self.trainer.name)
        result = self.run_import(f'name,email\nChanged,{self.learner.name}')
        self.assertEqual((result['updated'], len(result['errors'])), (0, 1))

    def test_trainer_needs_native_batch_authority(self):
        self.batch.set('instructors', [{'instructor': 'Administrator'}])
        self.batch.save(ignore_permissions=True)
        frappe.set_user(self.trainer.name)
        result = self.run_import(f'name,email,password,batchIds\nNew Learner,no-authority-{self.suffix}@example.test,N7!csvExamplePassword123,{self.batch.name}')
        self.assertEqual((result['created'], len(result['errors'])), (0, 1))

    def test_role_change_removes_old_role_and_process_access(self):
        result = self.run_import(f'name,email,role\nFormer Trainer,{self.trainer.name},learner')
        self.assertEqual(result, {'created': 0, 'updated': 1, 'errors': []})
        self.assertNotIn('BPO Trainer', frappe.get_roles(self.trainer.name))
        self.assertFalse(frappe.db.exists('BPO Process Access', {'member': self.trainer.name}))

    def test_native_validation_failure_rolls_back_new_user(self):
        # A full batch fails inside native enrollment validation, after User insert.
        self.batch.db_set('seat_count', 1)
        email = f'csv-full-{self.suffix}@example.test'
        hooks = (frappe.db.before_commit, frappe.db.after_commit, frappe.db.before_rollback, frappe.db.after_rollback)
        queued = [len(hook._functions) for hook in hooks]
        result = self.run_import(f'name,email,password,role,batchIds\nFull Batch,{email},N7!csvExamplePassword123,learner,{self.batch.name}')
        self.assertEqual((result['created'], result['updated'], len(result['errors'])), (0, 0, 1))
        self.assertFalse(frappe.db.exists('User', email))
        self.assertEqual([len(hook._functions) for hook in hooks], queued)
        self.assertNotIn('N7!csvExamplePassword123', str(result))

    def test_learner_and_guest_cannot_import(self):
        for user in (self.learner.name, 'Guest'):
            frappe.set_user(user)
            with self.assertRaises((frappe.PermissionError, frappe.AuthenticationError)):
                self.run_import('name,email\nExample,example@example.test')

    def test_duplicate_password_and_self_role_errors_do_not_modify_rows(self):
        result = self.run_import(f'name,email,password,role\nChanged,{self.learner.name},,\nDuplicate,{self.learner.name},,\nReset,{self.trainer.name},N7!csvExamplePassword123,\nBuiltin,Administrator,,learner')
        self.assertEqual((result['updated'], len(result['errors'])), (1, 3))

    def test_invalid_structure_writes_nothing(self):
        with self.assertRaises(frappe.ValidationError):
            self.run_import(f'name,email\nChanged,{self.learner.name}\nBroken')
        self.assertEqual(frappe.db.get_value('User', self.learner.name, 'full_name'), 'CSV learner')
