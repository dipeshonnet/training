"""Scoped CSV provisioning. Each row is saved or rolled back independently."""
import csv
import io
import re

import frappe
from frappe.rate_limiter import rate_limit
from bpo_coach.security import is_admin, is_staff, process_allowed, require_user

ROLES = {
    'learner': {'BPO Learner', 'LMS Student'},
    'trainer': {'BPO Trainer', 'Course Creator'},
    'admin': {'BPO Administrator', 'Moderator'},
}
MANAGED_ROLES = set().union(*ROLES.values())


class RowError(ValueError):
    pass


def parse_people_csv(source):
    if not isinstance(source, str) or len(source.encode('utf-8')) > 500_000:
        raise RowError('CSV must be smaller than 500 KB.')
    reader = csv.reader(io.StringIO(source.lstrip('\ufeff'), newline=''), strict=True)
    records = []
    try:
        while True:
            line = reader.line_num + 1
            cells = next(reader, None)
            if cells is None:
                break
            if any(cell.strip() for cell in cells):
                records.append((line, cells))
    except csv.Error:
        raise RowError('Invalid CSV quoting or field size.') from None
    if not records:
        raise RowError('CSV must include name and email headers.')
    headers = [cell.strip().lower() for cell in records.pop(0)[1]]
    allowed = {'name', 'email', 'password', 'role', 'batchids'}
    if not {'name', 'email'} <= set(headers):
        raise RowError('CSV must include name and email headers.')
    if len(headers) != len(set(headers)) or set(headers) - allowed:
        raise RowError('Use unique headers: name,email,password,role,batchIds.')
    if not 1 <= len(records) <= 100:
        raise RowError('Import between 1 and 100 people at a time.')
    rows = []
    for line, cells in records:
        if len(cells) != len(headers):
            raise RowError(f'Row {line} has the wrong number of columns.')
        row = dict(zip(headers, cells))
        row['row'] = line
        for field in ('name', 'email', 'role', 'batchids'):
            row[field] = row.get(field, '').strip()
        row['email'] = row['email'].lower()
        row['role'] = row['role'].lower()
        row.setdefault('password', '')
        rows.append(row)
    return rows


def save_person(row, admin):
    email, name = row['email'], row['name']
    if not 2 <= len(name) <= 120 or len(email) > 140 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise RowError('Provide a name (2–120 characters) and a valid email.')
    existing = frappe.db.get_value('User', {'email': email}, 'name')
    user = frappe.get_doc('User', existing) if existing else None
    if existing in ('Administrator', 'Guest'):
        raise RowError('Built-in accounts cannot be imported.')
    current_roles = set(frappe.get_roles(existing)) if existing else set()
    current_role = next((role for role in ('admin', 'trainer', 'learner') if ROLES[role] & current_roles), 'learner')
    role = row['role'] or current_role
    if role not in ROLES:
        raise RowError('Role must be learner, trainer, or admin.')
    if existing == frappe.session.user and row['role'] and role != current_role:
        raise RowError('You cannot change your own role.')
    if user and row['password']:
        raise RowError('Leave password blank for existing people. Reset passwords separately.')
    if not user and not 12 <= len(row['password']) <= 128:
        raise RowError('New accounts need a password of 12–128 characters.')
    batch_ids = list(dict.fromkeys(value.strip() for value in row['batchids'].split(';') if value.strip()))
    if len(batch_ids) > 100:
        raise RowError('Use at most 100 batch IDs per person.')
    if batch_ids and role != 'learner':
        raise RowError('Only learners can be enrolled in batches.')
    for batch in batch_ids:
        process = frappe.db.get_value('LMS Batch', batch, 'bpo_process')
        if not process or not process_allowed(process):
            raise RowError('A batch does not exist or is outside your process access.')
        if not admin:
            from lms.lms.permissions import can_author_batch
            if not can_author_batch(batch):
                raise RowError('Choose a batch where you are an instructor or evaluator.')
    if not admin:
        # v2 installs BPO Learner with desk_access, so Frappe automatically
        # classifies these users as System Users and adds the Desk User role.
        safe_roles = ROLES['learner'] | {'All', 'Guest', 'Desk User'}
        if role != 'learner' or (user and (current_role != 'learner' or current_roles - safe_roles)):
            raise RowError('Trainers can import learner accounts only.')
        if not user and not batch_ids:
            raise RowError('New learners need a batch in your assigned processes.')
        if user:
            batches = frappe.get_all('LMS Batch Enrollment', filters={'member': existing}, pluck='batch')
            processes = [frappe.db.get_value('LMS Batch', batch, 'bpo_process') for batch in batches]
            if not processes or any(not process or not process_allowed(process) for process in processes):
                raise RowError('This person is outside your process access.')
    if batch_ids and user and not user.enabled:
        raise RowError('Only active learners can be enrolled in batches.')
    # All authorization and field validation precedes writes. Frappe handles
    # password hashing, User validation and cache invalidation through save().
    if not user:
        user = frappe.get_doc(dict(doctype='User', email=email, first_name=name, enabled=1,
            send_welcome_email=0, new_password=row['password'], user_type='Website User'))
        user.set('roles', [{'role': value} for value in sorted(ROLES[role])])
        user.insert(ignore_permissions=True)
    else:
        user.first_name, user.middle_name, user.last_name = name, '', ''
        if row['role']:
            keep = {entry.role for entry in user.roles} - MANAGED_ROLES
            user.set('roles', [{'role': value} for value in sorted(keep | ROLES[role])])
        user.save(ignore_permissions=True)
        if role != 'trainer' and current_role == 'trainer':
            frappe.db.delete('BPO Process Access', {'member': existing})
    for batch in batch_ids:
        if not frappe.db.exists('LMS Batch Enrollment', {'batch': batch, 'member': user.name}):
            frappe.get_doc(dict(doctype='LMS Batch Enrollment', batch=batch, member=user.name)).insert(ignore_permissions=True)
    return 'updated' if existing else 'created'


@frappe.whitelist()
@rate_limit(limit=5, seconds=60)
def import_people(csv_text):
    require_user()
    if not is_staff():
        frappe.throw('Trainer access required.', frappe.PermissionError)
    if not frappe.request or frappe.request.method != 'POST':
        frappe.throw('Use POST for this operation.', frappe.PermissionError)
    try:
        rows = parse_people_csv(csv_text)
    except RowError as error:
        frappe.throw(str(error))
    result = {'created': 0, 'updated': 0, 'errors': []}
    seen = set()
    admin = is_admin()
    for row in rows:
        point = 'people_import_' + str(row['row'])
        # Frappe's savepoint rollback restores SQL only. User and enrollment
        # hooks also queue work after commit; failed rows must not retain it.
        hooks = (frappe.db.before_commit, frappe.db.after_commit,
                 frappe.db.before_rollback, frappe.db.after_rollback)
        hook_sizes = [len(hook._functions) for hook in hooks]
        frappe.db.savepoint(point)
        try:
            if row['email'] in seen:
                raise RowError('Duplicate email in this CSV.')
            seen.add(row['email'])
            result[save_person(row, admin)] += 1
        except Exception as error:
            frappe.db.rollback(save_point=point)
            frappe.clear_cache(user=row['email'])
            frappe.clear_document_cache('User', row['email'])
            for hook, size in zip(hooks, hook_sizes):
                while len(hook._functions) > size:
                    hook._functions.pop()
            # Never echo passwords, database errors or framework exception text.
            result['errors'].append({'row': row['row'], 'email': row['email'],
                'message': str(error) if isinstance(error, RowError) else 'Could not save this person. Check the account details and password policy, then retry.'})
        finally:
            frappe.db.release_savepoint(point)
    # Validation errors raised by caught User hooks must not turn partial success
    # into an HTTP error or disclose framework messages containing input values.
    frappe.clear_messages()
    return result
