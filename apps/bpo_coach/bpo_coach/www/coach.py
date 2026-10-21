import json
import frappe

no_cache = 1

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/coach'
        raise frappe.Redirect
    context.no_cache = 1
    context.full_width = True
    context.boot_json = json.dumps(dict(csrf_token=frappe.sessions.get_csrf_token(), user=frappe.session.user)).replace('<', '\\u003c')
