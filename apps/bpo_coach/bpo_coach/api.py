"""Authenticated application API. Learner responses never serialize full scenario documents."""
from contextlib import contextmanager
import base64
import csv
import hashlib
import io
import json
import uuid
from datetime import datetime
import frappe
from frappe.utils import now_datetime, get_datetime
from bpo_coach import engine
from bpo_coach.security import (require_user, require_admin, require_staff, is_admin, is_staff,
    process_allowed, insert, save, trusted_write, load_json, assignment_access, fingerprint, asset_allowed)
from bpo_coach.validation import validate_scenario

def read(value):
    return frappe.parse_json(value) if isinstance(value, str) else value

def uuid_value(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        frappe.throw('A UUID request identifier is required.')

def post():
    require_user()
    if frappe.request and frappe.request.method != 'POST':
        frappe.throw('Use POST for this operation.', frappe.PermissionError)

def events(attempt):
    rows = frappe.get_all('AI Action', filters={'attempt': attempt}, fields=['name', 'request_id', 'step_id', 'hotspot_id', 'input_value', 'correct', 'critical', 'creation'], order_by='creation asc, name asc')
    return [dict(id=r.name, request_id=r.request_id, step_id=r.step_id, hotspot_id=r.hotspot_id,
        value=r.input_value, correct=r.correct, critical=r.critical, created_at=r.creation) for r in rows]

def turns(attempt):
    rows = frappe.get_all('AI Dialogue', filters={'attempt': attempt}, fields=['name', 'request_id', 'sequence', 'agent_text', 'customer_text', 'state', 'error_message'], order_by='sequence asc')
    return [dict(id=r.name, **{k: r[k] for k in ('request_id', 'sequence', 'agent_text', 'customer_text', 'state', 'error_message')}) for r in rows]

def attempt_access(name, owner=False):
    require_user()
    a = frappe.get_doc('AI Attempt', name)
    assignment_access(a.assignment)
    if owner and a.member != frappe.session.user:
        frappe.throw('Only the assigned learner can execute this attempt.', frappe.PermissionError)
    return a

def scenario_of(attempt):
    return load_json(frappe.db.get_value('AI Scenario Version', attempt.scenario_version, 'content_json'))

@contextmanager
def attempt_lock(name):
    lock = frappe.cache.lock('bpo-attempt:' + name, timeout=120, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        frappe.throw('Another operation is running. Please retry.', frappe.ValidationError)
    try:
        yield
    except Exception:
        frappe.db.rollback()
        raise
    else:
        if not frappe.flags.in_test:
            frappe.db.commit()
    finally:
        lock.release()

def receipt(attempt, request_id, operation, payload):
    key = fingerprint([attempt, request_id])
    row = frappe.db.get_value('AI Operation', {'operation_key': key}, ['fingerprint', 'response_json', 'operation'], as_dict=True)
    if row:
        if row.fingerprint != fingerprint(payload) or row.operation != operation:
            frappe.throw('Request identifier was already used for a different operation.')
        return load_json(row.response_json)

def remember(attempt, request_id, operation, payload, response):
    insert('AI Operation', attempt=attempt, request_id=request_id, operation=operation,
        operation_key=fingerprint([attempt, request_id]), fingerprint=fingerprint(payload), response_json=json.dumps(response, default=str))

@frappe.whitelist()
def me():
    user = require_user()
    return {'user': user, 'name': frappe.db.get_value('User', user, 'full_name'), 'admin': is_admin(), 'staff': is_staff(), 'version': '2.0.0.dev0'}

@frappe.whitelist()
def workspace():
    user = require_user()
    assignments = frappe.get_all('BPO Training Assignment', fields=['name', 'member', 'batch', 'bpo_process as process', 'course', 'scenario_version', 'channels_json', 'bindings_json', 'mandatory', 'due_date', 'creation'], order_by='creation desc')
    from bpo_coach.completion import assignment_complete
    assignments = [dict(a, completed=assignment_complete(a)) for a in assignments if a.member == user or process_allowed(a.process)]
    attempts = frappe.get_all('AI Attempt', fields=['name', 'member', 'assignment', 'bpo_process as process', 'lesson', 'activity_id', 'scenario_version', 'mode', 'channel', 'status', 'grading_status', 'grading_error', 'result_json', 'submitted_at', 'creation'], order_by='creation desc')
    attempts = [dict(a, result=load_json(a.result_json)) for a in attempts if a.member == user or process_allowed(a.process)]
    for a in attempts:
        a.pop('result_json', None)
    processes = frappe.get_all('BPO Process', fields=['name', 'title', 'client'])
    processes = [p for p in processes if process_allowed(p.name)] if is_staff() else []
    scenarios = []
    if is_staff():
        scenarios = [s for s in frappe.get_all('AI Scenario', fields=['name', 'title', 'bpo_process as process', 'company_wide', 'draft_revision', 'published_version'], order_by='modified desc') if process_allowed(s.process)]
    courses = [c for c in frappe.get_all('LMS Course', fields=['name', 'title', 'published', 'bpo_process', 'bpo_company_wide', 'bpo_locked'])
        if __import__('bpo_coach.permissions', fromlist=['scope_course']).scope_course(c.name)]
    batches = [b for b in frappe.get_all('LMS Batch', fields=['name', 'title', 'bpo_process']) if process_allowed(b.bpo_process)] if is_staff() else []
    users = []
    if is_admin():
        users = frappe.get_all('User', filters={'enabled': 1, 'name': ['not in', ['Guest', 'Administrator']]}, fields=['name', 'full_name'])
    elif is_staff():
        members = {r.member for b in batches for r in frappe.get_all('LMS Batch Enrollment', filters={'batch': b.name}, fields=['member'])}
        users = [dict(name=m, full_name=frappe.db.get_value('User', m, 'full_name')) for m in sorted(members)]
    return dict(assignments=assignments, attempts=attempts, processes=processes, scenarios=scenarios, courses=courses, batches=batches, users=users,
        clients=frappe.get_all('BPO Client', fields=['name', 'title']) if is_admin() else [])

@frappe.whitelist()
def manage(kind: str, data):
    post()
    data = read(data)
    if not isinstance(data, dict):
        frappe.throw('Expected an object.')
    if kind in ('client', 'process', 'access', 'user', 'provider'):
        require_admin()
    if kind == 'client':
        return {'name': insert('BPO Client', title=str(data['title'])[:140], enabled=1).name}
    if kind == 'process':
        return {'name': insert('BPO Process', title=str(data['title'])[:140], client=data['client'], enabled=1).name}
    if kind == 'access':
        return {'name': insert('BPO Process Access', member=data['member'], bpo_process=data['process']).name}
    if kind == 'user':
        roles = {'learner': ['BPO Learner', 'LMS Student'], 'trainer': ['BPO Trainer', 'Course Creator'], 'admin': ['BPO Administrator', 'Moderator']}
        if data.get('role') not in roles:
            frappe.throw('Choose learner, trainer or admin.')
        u = frappe.get_doc(dict(doctype='User', email=data['email'], first_name=data['name'], enabled=1,
            send_welcome_email=0, new_password=data['password'], user_type='Website User'))
        u.insert(ignore_permissions=True)
        u.add_roles(*roles[data['role']])
        return {'name': u.name}
    if kind == 'provider':
        settings = frappe.get_single('AI Provider Settings')
        for k in ('api_key', 'text_model', 'stt_model', 'tts_model', 'tts_voice'):
            if data.get(k):
                settings.set(k, data[k])
        save(settings)
        return {'configured': bool(settings.get_password('api_key', raise_exception=False))}
    if kind in ('batch', 'course'):
        process = data.get('process')
        require_staff(process)
        if kind == 'batch':
            b = frappe.get_doc(dict(doctype='LMS Batch', title=data['title'], bpo_process=process,
                start_date=data['start_date'], end_date=data['end_date'], start_time='09:00:00', end_time='17:00:00', timezone='Asia/Kolkata', published=0))
            b.insert(ignore_permissions=True)
            return {'name': b.name}
        if data.get('company_wide'):
            require_admin()
        c = frappe.get_doc(dict(doctype='LMS Course', title=data['title'], short_introduction=data.get('description', 'Internal BPO training'),
            description=data.get('description', 'Internal BPO training'), bpo_process=process,
            bpo_company_wide=int(bool(data.get('company_wide'))), enable_certification=1,
            instructors=[{'instructor': frappe.session.user}]))
        c.insert(ignore_permissions=True)
        return {'name': c.name}
    if kind == 'batch_member':
        process = frappe.db.get_value('LMS Batch', data['batch'], 'bpo_process')
        require_staff(process)
        if not frappe.db.exists('User', {'name': data['member'], 'enabled': 1}):
            frappe.throw('Choose an active learner.')
        return {'name': frappe.get_doc(dict(doctype='LMS Batch Enrollment', batch=data['batch'], member=data['member'])).insert(ignore_permissions=True).name}
    frappe.throw('Unknown management operation.')

@frappe.whitelist()
def get_scenario(name: str):
    require_user()
    s = frappe.get_doc('AI Scenario', name)
    require_staff(s.bpo_process)
    return {'name': s.name, 'process': s.bpo_process, 'company_wide': s.company_wide, 'content': load_json(s.draft_json), 'revision': s.draft_revision, 'published_version': s.published_version}

@frappe.whitelist()
def save_scenario(content, process: str = None, name: str = None, revision: int = 0, company_wide: int = 0):
    post()
    require_staff(process)
    if company_wide:
        require_admin()
    try:
        content = validate_scenario(read(content))
    except ValueError as e:
        frappe.throw(str(e))
    for step in content['steps']:
        if step['assetId']:
            asset = frappe.get_doc('AI Asset', step['assetId'])
            if asset.bpo_process != process and not asset.company_wide:
                frappe.throw('Screenshot belongs to another process.')
    if name:
        frappe.db.get_value('AI Scenario', name, 'name', for_update=True)
        s = frappe.get_doc('AI Scenario', name)
        require_staff(s.bpo_process)
        if s.bpo_process != process or bool(s.company_wide) != bool(company_wide):
            frappe.throw('Scenario scope cannot be changed.')
        if s.draft_revision != int(revision):
            frappe.throw('Another edit was saved. Reload before saving again.')
        s.update(dict(title=content['title'], draft_json=json.dumps(content), draft_revision=s.draft_revision + 1))
        save(s)
    else:
        s = insert('AI Scenario', title=content['title'], bpo_process=process, company_wide=company_wide, draft_json=json.dumps(content), draft_revision=1)
    return {'name': s.name, 'revision': s.draft_revision}

@frappe.whitelist()
def publish(name: str, revision: int):
    post()
    frappe.db.get_value('AI Scenario', name, 'name', for_update=True)
    s = frappe.get_doc('AI Scenario', name)
    require_staff(s.bpo_process)
    if s.company_wide:
        require_admin()
    if s.draft_revision != int(revision):
        frappe.throw('Save the current draft before publishing.')
    try:
        content = validate_scenario(load_json(s.draft_json), publishing=True)
    except ValueError as e:
        frappe.throw(str(e))
    number = frappe.db.count('AI Scenario Version', {'scenario': s.name}) + 1
    v = insert('AI Scenario Version', scenario=s.name, version=number, version_key=f'{s.name}:{number}', bpo_process=s.bpo_process,
        company_wide=s.company_wide, content_json=json.dumps(content), content_hash=fingerprint(content), published_by=frappe.session.user)
    s.published_version = v.name
    save(s)
    return {'version': v.name, 'number': number}

@frappe.whitelist()
def upload_asset(process: str = None, company_wide: int = 0):
    post()
    require_staff(process)
    if int(company_wide):
        require_admin()
    from frappe.utils.file_manager import save_file
    file = frappe.request.files.get('file')
    if not file:
        frappe.throw('Choose a PNG, JPEG or WebP screenshot.')
    content = file.stream.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        frappe.throw('Screenshot exceeds 10 MB.')
    from PIL import Image
    image = Image.open(io.BytesIO(content))
    if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 40_000_000:
        frappe.throw('Unsupported screenshot format or dimensions.')
    image.verify()
    a = insert('AI Asset', bpo_process=process, company_wide=company_wide, filename=file.filename,
        checksum=hashlib.sha256(content).hexdigest())
    with trusted_write():
        stored = save_file(file.filename, content, 'AI Asset', a.name, is_private=1)
    a.file = stored.name
    save(a)
    return {'name': a.name, 'url': stored.file_url}

@frappe.whitelist()
def asset(name: str):
    require_user()
    a = frappe.get_doc('AI Asset', name)
    if not asset_allowed(a):
        frappe.throw('Screenshot access denied.', frappe.PermissionError)
    return {'url': frappe.db.get_value('File', a.file, 'file_url')}

@frappe.whitelist()
def assign(request_id: str, course: str = None, scenario_version: str = None, batch: str = None, member: str = None,
           process: str = None, channels=None, mandatory: int = 1, due_date: str = None):
    post()
    request_id = uuid_value(request_id)
    if bool(course) == bool(scenario_version) or bool(batch) == bool(member):
        frappe.throw('Choose a course or scenario, and a batch or individual learner.')
    if batch:
        process = frappe.db.get_value('LMS Batch', batch, 'bpo_process')
        members = frappe.get_all('LMS Batch Enrollment', filters={'batch': batch}, pluck='member')
    else:
        members = [member]
    require_staff(process)
    if not members:
        frappe.throw('The selected batch has no learners.')
    channels = read(channels) if channels else []
    from bpo_coach.completion import course_lessons, bindings
    activity_bindings = []
    if course:
        c = frappe.get_doc('LMS Course', course)
        if not c.published or (not c.bpo_company_wide and c.bpo_process != process):
            frappe.throw('Choose a published course in this process or a foundation course.')
        for lesson in course_lessons(course):
            activity_bindings.extend(bindings(frappe.get_doc('Course Lesson', lesson)))
    else:
        v = frappe.get_doc('AI Scenario Version', scenario_version)
        if not v.company_wide and v.bpo_process != process:
            frappe.throw('Scenario belongs to another process.')
        office = load_json(v.content_json)['office']
        channels = list(dict.fromkeys(channels))
        if not channels or set(channels) - ({'workflow'} if office == 'back' else {'chat', 'voice'}):
            frappe.throw('Choose workflow for back office, or chat/voice for front office.')
    ids = []
    for learner in members:
        if not frappe.db.exists('User', {'name': learner, 'enabled': 1}) or 'BPO Learner' not in frappe.get_roles(learner):
            frappe.throw('Assignments require active BPO learners.')
        if not is_admin() and not batch and not any(frappe.db.get_value('LMS Batch', b, 'bpo_process') == process for b in frappe.get_all('LMS Batch Enrollment', filters={'member': learner}, pluck='batch')):
            frappe.throw('Learner is outside your process.', frappe.PermissionError)
        key = fingerprint([request_id, learner])
        existing = frappe.db.get_value('BPO Training Assignment', {'assignment_key': key}, 'name')
        if existing:
            ids.append(existing)
            continue
        if course and not frappe.db.exists('LMS Enrollment', {'course': course, 'member': learner}):
            frappe.get_doc(dict(doctype='LMS Enrollment', course=course, member=learner, member_type='Student')).insert(ignore_permissions=True)
        a = insert('BPO Training Assignment', member=learner, batch=batch, bpo_process=process, course=course,
            scenario_version=scenario_version, channels_json=json.dumps(channels), bindings_json=json.dumps(activity_bindings),
            mandatory=int(bool(int(mandatory))), due_date=get_datetime(due_date) if due_date else None,
            assignment_key=key, assigned_by=frappe.session.user)
        ids.append(a.name)
    if course:
        frappe.db.set_value('LMS Course', course, 'bpo_locked', 1)
    return {'names': ids, 'count': len(ids)}

@frappe.whitelist()
def start(assignment: str, mode: str, channel: str, scenario_version: str = None, lesson: str = None, activity_id: str = None):
    post()
    a = assignment_access(assignment)
    if a.member != frappe.session.user or mode not in engine.MODES or channel not in engine.CHANNELS:
        frappe.throw('Invalid attempt request.', frappe.PermissionError)
    version = scenario_version or a.scenario_version
    if a.course:
        b = next((b for b in load_json(a.bindings_json, []) if b['version'] == version and b['lesson'] == lesson and b['activity'] == activity_id), None)
        if not b:
            frappe.throw('Activity is not assigned.', frappe.PermissionError)
        allowed = b['channels']
    else:
        if version != a.scenario_version or lesson:
            frappe.throw('Scenario is not assigned.', frappe.PermissionError)
        allowed = load_json(a.channels_json, [])
    if channel not in allowed:
        frappe.throw('Channel is not assigned.')
    key = fingerprint([a.name, version, lesson, activity_id, mode, channel])
    with frappe.cache.lock('bpo-start:' + key, timeout=20, blocking_timeout=5):
        name = frappe.db.get_value('AI Attempt', {'active_key': key}, 'name')
        if not name:
            attempt = insert('AI Attempt', member=a.member, bpo_process=a.bpo_process, assignment=a.name, lesson=lesson,
                activity_id=activity_id, scenario_version=version, mode=mode, channel=channel, started_at=now_datetime(), active_key=key)
            name = attempt.name
        frappe.db.commit()
    return get_attempt(name)

@frappe.whitelist()
def get_attempt(name: str):
    a = attempt_access(name)
    version = frappe.get_doc('AI Scenario Version', a.scenario_version)
    s = load_json(version.content_json)
    result = {k: a.get(k) for k in ('name', 'assignment', 'member', 'mode', 'channel', 'current_step', 'status', 'grading_status', 'grading_error', 'lesson', 'review_note')}
    result.update(scenario=engine.sanitize_scenario(s, a.mode, version.version), events=events(a.name), turns=turns(a.name), result=load_json(a.result_json))
    if a.member == frappe.session.user and a.mode == 'assessment' and a.status in ('active', 'grading'):
        result['events'] = [{k: v for k, v in e.items() if k not in ('correct', 'critical')} for e in result['events']]
    if a.channel != 'workflow':
        result['opening'] = s['opening']
    if a.member != frappe.session.user and process_allowed(a.bpo_process):
        result['review_context'] = {k: s[k] for k in ('reference', 'outcome', 'threshold')}
    return result

@frappe.whitelist()
def action(attempt: str, request_id: str, step_id: str, hotspot_id: str = None, value: str = ''):
    post()
    request_id = uuid_value(request_id)
    if not isinstance(value, str) or len(value) > 500:
        frappe.throw('Input exceeds 500 characters.')
    payload = [step_id, hotspot_id, value]
    with attempt_lock(attempt):
        a = attempt_access(attempt, owner=True)
        prior = receipt(a.name, request_id, 'action', payload)
        if prior is not None:
            return prior
        if a.status != 'active':
            frappe.throw('This attempt is no longer active.')
        s = scenario_of(a)
        if a.current_step >= len(s['steps']) or s['steps'][a.current_step]['id'] != step_id:
            frappe.throw('This is not the current step.')
        result = engine.validate_action(s, a.current_step, hotspot_id, value)
        insert('AI Action', attempt=a.name, request_id=request_id, event_key=fingerprint([a.name, request_id]), step_id=step_id,
            hotspot_id=hotspot_id, input_value=value, correct=int(result['correct']), critical=int(result['critical']))
        if engine.completed_step(s, a.current_step, events(a.name)):
            a.current_step += 1
            save(a)
        response = {'current_step': a.current_step}
        if a.mode != 'assessment':
            response['correct'] = result['correct']
            response['hint'] = s['steps'][min(a.current_step, len(s['steps']) - 1)]['hint']
        remember(a.name, request_id, 'action', payload, response)
        return response

@frappe.whitelist()
def conversation(attempt: str, request_id: str, text: str = None, retry_turn: str = None):
    post()
    request_id = uuid_value(request_id)
    from bpo_coach.provider import customer_reply, transcribe
    with attempt_lock(attempt):
        a = attempt_access(attempt, owner=True)
        if a.status != 'active' or a.channel == 'workflow':
            frappe.throw('Conversation is unavailable for this attempt.')
        payload = [text, retry_turn, a.channel]
        prior = receipt(a.name, request_id, 'conversation', payload)
        if prior is not None:
            return prior
        t = None
        if retry_turn:
            t = frappe.get_doc('AI Dialogue', retry_turn)
            if t.attempt != a.name or t.state != 'failed':
                frappe.throw('Only a failed reply in this attempt can be retried.')
        else:
            existing = frappe.db.get_value('AI Dialogue', {'turn_key': fingerprint([a.name, request_id])}, 'name')
            if existing:
                t = frappe.get_doc('AI Dialogue', existing)
                if t.state == 'completed':
                    return {'turn': t.name, 'text': t.customer_text}
            elif any(t['state'] != 'completed' for t in turns(a.name)):
                frappe.throw('Retry the unfinished reply first.')
            else:
                audio = frappe.request.files.get('file') if a.channel == 'voice' else None
                if a.channel == 'voice':
                    if not audio:
                        frappe.throw('Record a response for the voice channel.')
                    text = transcribe(audio)
                if not isinstance(text, str) or not text.strip() or len(text) > 8000:
                    frappe.throw('Enter a response of up to 8000 characters.')
                t = insert('AI Dialogue', attempt=a.name, request_id=request_id, turn_key=fingerprint([a.name, request_id]),
                    sequence=len(turns(a.name)) + 1, agent_text=text, state='pending')
                frappe.db.commit()
        try:
            t.customer_text = customer_reply(scenario_of(a), turns(a.name), t.agent_text, a.current_step, a.mode)
            t.state = 'completed'
            t.error_message = None
            save(t)
            response = {'turn': t.name, 'text': t.customer_text}
            remember(a.name, request_id, 'conversation', payload, response)
            return response
        except Exception:
            t.state = 'failed'
            t.error_message = 'AI reply failed. Your response is saved; retry this turn.'
            save(t)
            frappe.db.commit()
            raise

@frappe.whitelist()
def speech(attempt: str, turn: str = None):
    post()
    a = attempt_access(attempt, owner=True)
    if a.channel != 'voice':
        frappe.throw('Speech is available in voice attempts only.')
    from bpo_coach.provider import synthesize
    if turn:
        t = frappe.get_doc('AI Dialogue', turn)
        if t.attempt != a.name or t.state != 'completed':
            frappe.throw('This reply is not available.')
        text = t.customer_text
    else:
        text = scenario_of(a)['opening']
    content = synthesize(text)
    frappe.local.response.update(type='download', filename='reply.wav', filecontent=content, display_content_as='inline', content_type='audio/wav')

@frappe.whitelist()
def coaching(attempt: str):
    post()
    a = attempt_access(attempt, owner=True)
    if a.mode == 'assessment':
        frappe.throw('Coaching is unavailable during assessment.', frappe.PermissionError)
    from bpo_coach.provider import coach
    return {'text': coach(scenario_of(a), events(a.name), turns(a.name))}

@frappe.whitelist()
def submit(attempt: str, request_id: str):
    post()
    uuid_value(request_id)
    with attempt_lock(attempt):
        a = attempt_access(attempt, owner=True)
        if a.status != 'active':
            return {'name': a.name, 'status': a.status, 'grading_status': a.grading_status}
        if any(t['state'] != 'completed' for t in turns(a.name)):
            frappe.throw('Retry unfinished customer replies before submitting.')
        if a.channel != 'workflow' and a.mode != 'walkthrough' and not turns(a.name):
            frappe.throw('Complete at least one conversation turn.')
        a.submitted_at = now_datetime()
        a.active_key = None
        a.status = 'submitted' if a.mode == 'walkthrough' else 'grading'
        a.grading_status = 'completed' if a.mode == 'walkthrough' else 'queued'
        a.grading_generation = int(a.grading_generation or 0) + 1
        save(a)
        if a.mode != 'walkthrough':
            frappe.enqueue('bpo_coach.jobs.grade', attempt=a.name, generation=a.grading_generation, queue='long', enqueue_after_commit=True)
        return {'name': a.name, 'status': a.status, 'grading_status': a.grading_status}

@frappe.whitelist()
def retry_grading(attempt: str):
    post()
    with attempt_lock(attempt):
        a = attempt_access(attempt)
        if a.grading_status != 'failed':
            frappe.throw('Only failed grading can be retried.')
        a.grading_status = 'queued'
        a.grading_error = None
        a.grading_generation = int(a.grading_generation or 0) + 1
        save(a)
        frappe.enqueue('bpo_coach.jobs.grade', attempt=a.name, generation=a.grading_generation, queue='long', enqueue_after_commit=True)
        return {'queued': True}

@frappe.whitelist()
def review(attempt: str, decision: str, note: str = ''):
    post()
    if decision not in ('approved', 'retry') or not isinstance(note, str) or len(note) > 4000:
        frappe.throw('Invalid review decision.')
    with attempt_lock(attempt):
        a = attempt_access(attempt)
        require_staff(a.bpo_process)
        if a.mode != 'assessment' or a.status != 'submitted' or a.grading_status != 'completed':
            frappe.throw('Only graded, submitted assessments can be reviewed.')
        result = load_json(a.result_json)
        if decision == 'approved' and (not result.get('passed') or not result.get('criticalPassed')):
            frappe.throw('Assessment must pass all critical checks before approval.')
        if decision == 'retry' and not note.strip():
            frappe.throw('Explain what the learner should practice.')
        a.status, a.review_note, a.reviewed_by, a.reviewed_at = decision, note, frappe.session.user, now_datetime()
        save(a)
        if decision == 'approved':
            from bpo_coach.completion import advance_after_review
            advance_after_review(a)
        return {'status': a.status}

@frappe.whitelist()
def report(export: int = 0):
    require_user()
    if not is_staff():
        frappe.throw('Trainer access required.', frappe.PermissionError)
    data = workspace()
    attempts, assignments = data['attempts'], data['assignments']
    summary = engine.first_attempt_metrics(attempts)
    summary.update(assignments=len(assignments), completed=sum(a['completed'] for a in assignments),
        overdue=sum(bool(not a['completed'] and a['due_date'] and get_datetime(a['due_date']) < now_datetime()) for a in assignments),
        review_backlog=sum(a['mode'] == 'assessment' and a['status'] == 'submitted' and a['grading_status'] == 'completed' for a in attempts))
    if int(export):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(['Assignment', 'Learner', 'Process', 'Course', 'Scenario version', 'Mandatory', 'Due date', 'Completed'])
        for a in assignments:
            # Prevent spreadsheet formula injection in names and titles.
            row = [a['name'], a['member'], a['process'], a['course'], a['scenario_version'], a['mandatory'], a['due_date'], a['completed']]
            writer.writerow(["'" + str(v) if str(v).startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in row])
        frappe.local.response.update(type='download', filename='ai-coach-report.csv', filecontent=out.getvalue(), content_type='text/csv')
    else:
        return {'summary': summary, 'assignments': assignments, 'attempts': attempts}
