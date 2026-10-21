import frappe
from bpo_coach.security import is_admin, is_staff, process_allowed, asset_allowed, load_json, internal_write

def scope_course(course, user=None, write=False):
    user = user or frappe.session.user
    if user == 'Guest':
        return False
    if is_admin(user):
        return True
    row = frappe.db.get_value('LMS Course', course, ['bpo_process', 'bpo_company_wide', 'published'], as_dict=True)
    if not row:
        return False
    if write:
        return bool(not row.bpo_company_wide and process_allowed(row.bpo_process, user))
    if not row.published and not process_allowed(row.bpo_process, user):
        return False
    return bool(row.bpo_company_wide or process_allowed(row.bpo_process, user) or frappe.db.exists(
        'BPO Training Assignment', {'course': course, 'member': user}))

def course_query(user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return ''
    if user == 'Guest':
        return '1=0'
    u = frappe.db.escape(user)
    clauses = ['(`tabLMS Course`.bpo_company_wide=1 AND `tabLMS Course`.published=1)',
               f"""(`tabLMS Course`.published=1 AND `tabLMS Course`.name IN
                 (SELECT course FROM `tabBPO Training Assignment` WHERE member={u}))"""]
    if is_staff(user):
        clauses.append(f"""`tabLMS Course`.bpo_process IN
          (SELECT bpo_process FROM `tabBPO Process Access` WHERE member={u})""")
    return '(' + ' OR '.join(clauses) + ')'

def native_permission(doc, ptype='read', user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return True
    write = ptype not in ('read', 'select', 'print')
    if doc.doctype == 'LMS Course':
        if doc.is_new():
            return is_staff(user) and process_allowed(doc.get('bpo_process'), user) and not doc.get('bpo_company_wide')
        return scope_course(doc.name, user, write)
    if doc.doctype == 'LMS Batch':
        return process_allowed(doc.get('bpo_process'), user) if write else bool(process_allowed(doc.get('bpo_process'), user) or frappe.db.exists('LMS Batch Enrollment', {'batch': doc.name, 'member': user}))
    if doc.doctype == 'File':
        return file_permission(doc, ptype, user)
    course = doc.get('course')
    if not course and doc.get('lesson'):
        course = frappe.db.get_value('Course Lesson', doc.lesson, 'course')
    if doc.doctype == 'Course Chapter':
        course = doc.get('course')
    if course:
        if not scope_course(course, user, write and doc.doctype not in ('LMS Enrollment', 'LMS Course Progress', 'LMS Quiz Submission', 'LMS Assignment Submission')):
            return False
        if doc.get('member') and not process_allowed(frappe.db.get_value('LMS Course', course, 'bpo_process'), user):
            return doc.member == user and ptype in ('read', 'select', 'print')
    return None

def file_permission(doc, ptype='read', user=None):
    if user == 'Guest' or (user is None and frappe.session.user == 'Guest'):
        return False
    if doc.attached_to_doctype == 'AI Asset':
        return ptype in ('read', 'select', 'print') and asset_allowed(frappe.get_doc('AI Asset', doc.attached_to_name), user)
    if doc.attached_to_doctype in ('LMS Course', 'Course Lesson', 'Course Chapter'):
        course = doc.attached_to_name if doc.attached_to_doctype == 'LMS Course' else frappe.db.get_value(doc.attached_to_doctype, doc.attached_to_name, 'course')
        if not scope_course(course, user):
            return False
    from lms.lms.permissions import file_has_permission
    return file_has_permission(doc, ptype, user)

def validate_scope(doc, method=None):
    if internal_write():
        return
    if doc.doctype in ('LMS Course', 'LMS Batch'):
        if not is_admin() and (not process_allowed(doc.get('bpo_process')) or doc.get('bpo_company_wide')):
            frappe.throw('This scope requires administrator or process access.', frappe.PermissionError)
        old = doc.get_doc_before_save()
        if old and old.get('bpo_locked'):
            fields = ['chapters', 'bpo_process', 'bpo_company_wide', 'bpo_locked'] if doc.doctype == 'LMS Course' else ['bpo_process']
            if any(old.get(k) != doc.get(k) for k in fields):
                frappe.throw('Assigned curricula are locked. Duplicate the course for revisions.')
        if doc.doctype == 'LMS Course' and doc.published:
            from bpo_coach.completion import course_lessons, bindings, assessment_ids
            for name in course_lessons(doc.name):
                lesson = frappe.get_doc('Course Lesson', name)
                bindings(lesson)
                quizzes, _ = assessment_ids(lesson)
                if any(not frappe.db.count('LMS Quiz Question', {'parent': q}) for q in quizzes):
                    frappe.throw('Required quizzes cannot be empty.')
    elif doc.doctype in ('Course Chapter', 'Course Lesson'):
        course = doc.get('course')
        old = doc.get_doc_before_save()
        for c in {course, old.get('course') if old else None} - {None}:
            if not scope_course(c, write=True):
                frappe.throw('Course authoring access denied.', frappe.PermissionError)
            if frappe.db.get_value('LMS Course', c, 'bpo_locked'):
                frappe.throw('Assigned curricula are locked. Duplicate the course for revisions.')
        if doc.doctype == 'Course Lesson':
            from bpo_coach.completion import bindings
            for b in bindings(doc):
                version = frappe.get_doc('AI Scenario Version', b['version'])
                if version.bpo_process and version.bpo_process != frappe.db.get_value('LMS Course', course, 'bpo_process'):
                    frappe.throw('AI activity belongs to another process.')
    elif doc.doctype == 'File' and doc.attached_to_doctype in ('AI Asset', 'LMS Course', 'Course Lesson', 'Course Chapter') and not doc.is_private:
        frappe.throw('Training files must use private storage.')

def protect_delete(doc, method=None):
    course = doc.name if doc.doctype == 'LMS Course' else doc.get('course')
    if course and frappe.db.get_value('LMS Course', course, 'bpo_locked'):
        frappe.throw('Assigned curricula cannot be deleted.')

def custom_permission(doc, ptype='read', user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return True
    if ptype not in ('read', 'select', 'print'):
        return False
    if doc.doctype in ('AI Scenario', 'AI Scenario Version'):
        return process_allowed(doc.get('bpo_process'), user)
    if doc.doctype == 'AI Asset':
        return asset_allowed(doc, user)
    if doc.doctype in ('AI Action', 'AI Dialogue', 'AI Operation'):
        return False
    if doc.get('member') == user:
        return True
    return process_allowed(doc.get('bpo_process'), user)

def deny_query(user=None):
    return '' if is_admin(user) else '1=0'

def before_request():
    # The portal is internal even when native LMS routes normally allow guests.
    path = frappe.request.path
    if frappe.session.user == 'Guest' and (path.startswith('/lms') or path.startswith('/coach') or path.startswith('/api/method/lms.') or path.startswith('/api/method/bpo_coach.')):
        frappe.throw('Please sign in.', frappe.AuthenticationError)
