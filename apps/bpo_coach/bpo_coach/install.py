import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def ensure_roles():
    for role in ('BPO Administrator', 'BPO Trainer', 'BPO Learner'):
        if not frappe.db.exists('Role', role):
            frappe.get_doc({'doctype': 'Role', 'role_name': role, 'desk_access': 1}).insert(ignore_permissions=True)


def after_install():
    after_migrate()


def setup_defaults():
    # Frappe commits the installed-app marker before calling after_install.
    # A migrate retry must finish interrupted setup without resetting later
    # administrator changes on every container restart.
    if frappe.db.get_global('bpo_coach_setup_complete'):
        return
    for dt, values in {
        'System Settings': {'language': 'en', 'time_zone': 'Asia/Kolkata'},
        'Website Settings': {'home_page': 'coach', 'app_name': 'AI Coach', 'disable_signup': 1},
    }.items():
        doc = frappe.get_single(dt)
        for key, value in values.items():
            if doc.meta.has_field(key):
                doc.set(key, value)
        doc.save(ignore_permissions=True)
    admin = frappe.get_doc('User', 'Administrator')
    admin.add_roles('BPO Administrator')
    frappe.db.set_global('bpo_coach_setup_complete', '1')

def after_migrate():
    ensure_roles()
    create_custom_fields({
        'LMS Course': [
            dict(fieldname='bpo_process', label='BPO Process', fieldtype='Link', options='BPO Process', insert_after='title'),
            dict(fieldname='bpo_company_wide', label='Company-wide foundation', fieldtype='Check', default='0', insert_after='bpo_process'),
            dict(fieldname='bpo_locked', label='Assigned curriculum locked', fieldtype='Check', default='0', read_only=1, insert_after='bpo_company_wide'),
        ],
        'LMS Batch': [dict(fieldname='bpo_process', label='BPO Process', fieldtype='Link', options='BPO Process', insert_after='title')],
    }, update=True)
    for dt, columns in [('AI Attempt', ['assignment', 'member', 'scenario_version', 'channel']), ('AI Action', ['attempt']), ('AI Dialogue', ['attempt', 'sequence']), ('BPO Training Assignment', ['member', 'course']), ('BPO Process Access', ['member', 'bpo_process'])]:
        frappe.db.add_index(dt, columns)
    setup_defaults()
