from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo
import frappe
from frappe.utils import now_datetime, get_datetime
from bpo_coach.security import save, insert

def grade(attempt, generation):
    from bpo_coach.api import attempt_lock, scenario_of, events, turns
    from bpo_coach.provider import evaluate
    from bpo_coach.engine import aggregate_assessment
    with attempt_lock(attempt):
        a = frappe.get_doc('AI Attempt', attempt)
        if a.status != 'grading' or a.grading_status not in ('queued', 'running') or a.grading_generation != generation:
            return
        a.grading_status, a.grading_started_at = 'running', now_datetime()
        save(a)
        frappe.db.commit()
        try:
            s = scenario_of(a)
            graded = evaluate(s, events(a.name), turns(a.name), a.channel)
            # Elapsed time ends at submission, so a worker backlog does not penalize learners.
            elapsed = (get_datetime(a.submitted_at) - get_datetime(a.started_at)).total_seconds() * 1000
            result = aggregate_assessment(s, graded['criteria'], 0, elapsed, graded['strengths'], graded['improvements'])
            a.result_json = json.dumps(result)
            a.status, a.grading_status, a.grading_error = 'submitted', 'completed', None
        except Exception:
            a.grading_status = 'failed'
            a.grading_error = 'Grading could not complete. Evidence is saved; retry grading.'
            frappe.log_error(title='AI Coach grading failed')
        save(a)

def recover_grading():
    now = now_datetime()
    for row in frappe.get_all('AI Attempt', filters={'status': 'grading', 'grading_status': ['in', ['queued', 'running']]}, fields=['name', 'grading_status', 'grading_started_at', 'modified', 'grading_generation']):
        time = row.grading_started_at if row.grading_status == 'running' else row.modified
        if get_datetime(time) > now - timedelta(minutes=3):
            continue
        if row.grading_status == 'running':
            from bpo_coach.api import attempt_lock
            with attempt_lock(row.name):
                a = frappe.get_doc('AI Attempt', row.name)
                if a.grading_status != 'running':
                    continue
                a.grading_status, a.grading_error = 'failed', 'Grading was interrupted. Retry to continue.'
                save(a)
        else:
            frappe.enqueue('bpo_coach.jobs.grade', attempt=row.name, generation=row.grading_generation, queue='long')
    # HTTP workers may die after saving a pending reply. A learner can then retry it.
    for row in frappe.get_all('AI Dialogue', filters={'state': 'pending', 'modified': ['<', now - timedelta(minutes=3)]}, fields=['name', 'attempt']):
        lock = frappe.cache.lock('bpo-attempt:' + row.attempt, timeout=10, blocking_timeout=0)
        if lock.acquire(blocking=False):
            try:
                t = frappe.get_doc('AI Dialogue', row.name)
                if t.state == 'pending':
                    t.state, t.error_message = 'failed', 'Reply was interrupted. Retry this turn.'
                    save(t)
                    frappe.db.commit()
            finally:
                lock.release()

def reminders():
    # Explicit local time avoids relying on the scheduler container's timezone.
    now = datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None)
    if now.hour != 9:
        return
    from bpo_coach.completion import assignment_complete
    for name in frappe.get_all('BPO Training Assignment', filters={'due_date': ['<=', now + timedelta(hours=48)]}, pluck='name'):
        a = frappe.get_doc('BPO Training Assignment', name)
        if not a.due_date or assignment_complete(a):
            continue
        category = 'overdue' if get_datetime(a.due_date) < now else 'due_soon'
        key = f'{a.name}|{category}|{now.date()}'
        if frappe.db.exists('BPO Reminder', {'reminder_key': key}):
            continue
        try:
            insert('BPO Reminder', reminder_key=key, assignment=a.name, member=a.member, category=category, local_date=now.date())
            frappe.get_doc(dict(doctype='Notification Log', subject='Training overdue' if category == 'overdue' else 'Training due soon',
                for_user=a.member, type='Alert', document_type=a.doctype, document_name=a.name,
                email_content='Open AI Coach to resume your assigned training.')).insert(ignore_permissions=True)
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            frappe.db.rollback()
