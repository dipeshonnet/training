"""Server-only write authority. Request JSON cannot set a ContextVar."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import frappe

_internal = ContextVar('bpo_internal_write', default=False)

@contextmanager
def trusted_write():
    token = _internal.set(True)
    try:
        yield
    finally:
        _internal.reset(token)

def internal_write():
    return _internal.get()

def require_user():
    if frappe.session.user == 'Guest':
        frappe.throw('Please sign in.', frappe.AuthenticationError)
    return frappe.session.user

def is_admin(user=None):
    user = user or frappe.session.user
    return user == 'Administrator' or 'BPO Administrator' in frappe.get_roles(user)

def is_staff(user=None):
    return is_admin(user) or 'BPO Trainer' in frappe.get_roles(user or frappe.session.user)

def require_admin():
    require_user()
    if not is_admin():
        frappe.throw('Administrator access required.', frappe.PermissionError)

def require_staff(process=None):
    require_user()
    if not is_staff() or not process_allowed(process):
        frappe.throw('This process is outside your access.', frappe.PermissionError)

def process_allowed(process, user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return True
    return bool(process and 'BPO Trainer' in frappe.get_roles(user) and frappe.db.exists(
        'BPO Process Access', {'member': user, 'bpo_process': process}))

def insert(doctype, **values):
    with trusted_write():
        return frappe.get_doc(dict(doctype=doctype, **values)).insert(ignore_permissions=True)

def save(doc):
    with trusted_write():
        return doc.save(ignore_permissions=True)

def load_json(value, default=None):
    if value is None or value == '':
        return default if default is not None else {}
    return json.loads(value) if isinstance(value, str) else value

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def assignment_access(name, user=None):
    doc = frappe.get_doc('BPO Training Assignment', name)
    user = user or frappe.session.user
    if doc.member != user and not process_allowed(doc.bpo_process, user):
        frappe.throw('Assignment access denied.', frappe.PermissionError)
    return doc

def version_for_assignment(assignment, version_name, lesson=None):
    if assignment.course:
        bindings = load_json(assignment.bindings_json, [])
        binding = next((b for b in bindings if b['version'] == version_name and b['lesson'] == lesson), None)
        if not binding:
            frappe.throw('Activity is not part of this assignment.', frappe.PermissionError)
        return binding['channels']
    if assignment.scenario_version != version_name or lesson:
        frappe.throw('Activity is not assigned.', frappe.PermissionError)
    return load_json(assignment.channels_json, [])

def asset_allowed(asset, user=None):
    user = user or frappe.session.user
    if process_allowed(asset.bpo_process, user):
        return True
    for a in frappe.get_all('BPO Training Assignment', filters={'member': user}, fields=['scenario_version', 'bindings_json']):
        versions = [a.scenario_version] if a.scenario_version else [b['version'] for b in load_json(a.bindings_json, [])]
        for version in versions:
            s = load_json(frappe.db.get_value('AI Scenario Version', version, 'content_json'))
            if any(step['assetId'] == asset.name for step in s.get('steps', [])):
                return True
    return False
