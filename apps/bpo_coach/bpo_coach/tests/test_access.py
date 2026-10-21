"""Exercise training visibility through Frappe's real permission and query paths."""
import frappe
from frappe.tests import IntegrationTestCase

from bpo_coach.api import workspace
from bpo_coach import native
from bpo_coach.permissions import scope_course
from bpo_coach.security import insert


class TestCourseAccess(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.previous_user = frappe.session.user
        frappe.set_user('Administrator')
        self.addCleanup(frappe.set_user, self.previous_user)
        suffix = frappe.generate_hash(length=10)
        self.learner = f'visibility-{suffix}@example.test'
        user = frappe.get_doc(dict(doctype='User', email=self.learner,
                                   first_name='Visibility learner', send_welcome_email=0,
                                   user_type='Website User')).insert(ignore_permissions=True)
        user.add_roles('LMS Student', 'BPO Learner')
        self.client = insert('BPO Client', title=f'Visibility client {suffix}', enabled=1)
        self.process = insert('BPO Process', title=f'Visibility process {suffix}',
                              client=self.client.name, enabled=1)
        self.draft = self.course(f'Foundation draft {suffix}', company_wide=1, published=0)
        self.foundation = self.course(f'Published foundation {suffix}', company_wide=1, published=1)
        self.scoped = self.course(f'Scoped course {suffix}', published=1)

    def course(self, title, company_wide=0, published=0):
        return insert('LMS Course', title=title, description='Visibility integration fixture',
                      short_introduction='Visibility integration fixture',
                      bpo_process=None if company_wide else self.process.name,
                      bpo_company_wide=company_wide, published=published,
                      notification_sent=1, instructors=[{'instructor': 'Administrator'}])

    def test_learner_cannot_read_unpublished_foundations(self):
        frappe.set_user(self.learner)
        self.assertFalse(scope_course(self.draft.name))
        self.assertFalse(frappe.has_permission('LMS Course', doc=self.draft))
        self.assertTrue(scope_course(self.foundation.name))
        self.assertFalse(scope_course(self.scoped.name))

    def test_course_queries_and_workspace_hide_unpublished_foundations(self):
        frappe.set_user(self.learner)
        # LMS deliberately grants learners course reads through its scoped
        # endpoints, without granting a generic REST list permission.
        with self.assertRaises(frappe.PermissionError):
            frappe.get_list('LMS Course',
                            filters={'name': ['in', [self.draft.name, self.foundation.name, self.scoped.name]]},
                            fields=['name'])
        names = {row.name for row in workspace()['courses']}
        self.assertNotIn(self.draft.name, names)
        self.assertIn(self.foundation.name, names)
        self.assertNotIn(self.scoped.name, names)

    def test_guest_cannot_read_training_courses(self):
        frappe.set_user('Guest')
        for course in (self.draft, self.foundation, self.scoped):
            self.assertFalse(scope_course(course.name))
            self.assertFalse(frappe.has_permission('LMS Course', doc=course))

    def test_native_catalog_count_and_details_apply_training_scope(self):
        frappe.set_user(self.learner)
        filters = {'name': ['in', [self.draft.name, self.foundation.name, self.scoped.name]]}
        self.assertEqual([row.name for row in native.get_courses(filters)], [self.foundation.name])
        self.assertEqual(native.get_course_count(filters), 1)
        self.assertEqual(native.get_course_details(self.scoped.name), {})
        self.assertEqual(native.get_course_outline(self.scoped.name), [])
        with self.assertRaises(frappe.PermissionError):
            native.get_lesson(self.scoped.name, 1, 1)
        self.assertEqual(frappe.override_whitelisted_method('lms.lms.utils.get_courses'),
                         'bpo_coach.native.get_courses')

    def test_native_virtual_filters_cannot_replace_training_scope(self):
        # A native enrollment is not a training assignment. It must not grant
        # access to a different process through the catalog's enrolled tab.
        insert('LMS Enrollment', member=self.learner, course=self.scoped.name)
        frappe.set_user(self.learner)
        self.assertEqual(native.get_courses({'enrolled': 1}), [])
        self.assertEqual(native.get_course_count({'enrolled': 1}), 0)

    def test_featured_catalog_pagination_and_count_use_the_same_scope(self):
        extra = self.course('Second ' + self.foundation.title, company_wide=1, published=1)
        self.foundation.db_set('featured', 1)
        self.scoped.db_set('featured', 1)
        filters = {'live': 1, 'name': ['in', [self.foundation.name, self.scoped.name, extra.name]]}
        frappe.set_user(self.learner)
        pages = [native.get_courses(filters, start=index, limit_page_length=1) for index in range(3)]
        self.assertEqual([[row.name for row in page] for page in pages],
                         [[self.foundation.name], [extra.name], []])
        self.assertEqual(native.get_course_count(filters), 2)
