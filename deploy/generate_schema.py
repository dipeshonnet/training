"""Generate checked-in Frappe metadata from the compact schema below."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'apps/bpo_coach/bpo_coach/bpo_coach/doctype'

def field(name, kind='Data', options=None, required=False, **extra):
    d = dict(fieldname=name, label=name.replace('_', ' ').title(), fieldtype=kind, **extra)
    if options is not None:
        d['options'] = options
    if required:
        d['reqd'] = 1
    return d

def link(name, target, **kw):
    return field(name, 'Link', target, **kw)

scope = [link('process', 'BPO Process'), field('company_wide', 'Check', default='0')]
schemas = {
    'BPO Client': [field('title', required=True), field('enabled', 'Check', default='1')],
    'BPO Process': [field('title', required=True), link('client', 'BPO Client', required=True), field('enabled', 'Check', default='1')],
    'BPO Process Access': [link('member', 'User', required=True), link('process', 'BPO Process', required=True), field('access_key', unique=1, hidden=1)],
    'AI Scenario': [field('title', required=True), *scope, field('draft_json', 'Long Text', required=True), field('draft_revision', 'Int', default='1'), link('published_version', 'AI Scenario Version')],
    'AI Scenario Version': [link('scenario', 'AI Scenario', required=True), field('version', 'Int', required=True), *scope, field('version_key', unique=1), field('content_json', 'Long Text', required=True), field('content_hash'), link('published_by', 'User')],
    'AI Asset': [*scope, link('file', 'File'), field('filename'), field('checksum')],
    'BPO Training Assignment': [link('member', 'User', required=True), link('batch', 'LMS Batch'), link('process', 'BPO Process'), link('course', 'LMS Course'), link('scenario_version', 'AI Scenario Version'), field('channels_json', 'Long Text'), field('bindings_json', 'Long Text'), field('mandatory', 'Check', default='1'), field('due_date', 'Datetime'), field('assignment_key', unique=1), link('assigned_by', 'User')],
    'AI Attempt': [link('member', 'User', required=True), link('process', 'BPO Process'), link('assignment', 'BPO Training Assignment', required=True), link('lesson', 'Course Lesson'), link('scenario_version', 'AI Scenario Version', required=True), field('mode', 'Select', 'walkthrough\npractice\nassessment', required=True), field('channel', 'Select', 'workflow\nchat\nvoice', required=True), field('status', 'Select', 'active\ngrading\nsubmitted\napproved\nretry', default='active'), field('grading_status', 'Select', 'not_started\nqueued\nrunning\nfailed\ncompleted', default='not_started'), field('current_step', 'Int'), field('started_at', 'Datetime'), field('submitted_at', 'Datetime'), field('grading_started_at', 'Datetime'), field('grading_generation', 'Int'), field('grading_error', 'Small Text'), field('result_json', 'Long Text'), field('review_note', 'Small Text'), link('reviewed_by', 'User'), field('reviewed_at', 'Datetime'), field('active_key', unique=1)],
    'AI Action': [link('attempt', 'AI Attempt', required=True), field('request_id', required=True), field('event_key', unique=1), field('step_id'), field('hotspot_id'), field('input_value', 'Small Text'), field('correct', 'Check'), field('critical', 'Check')],
    'AI Dialogue': [link('attempt', 'AI Attempt', required=True), field('request_id', required=True), field('turn_key', unique=1), field('sequence', 'Int'), field('agent_text', 'Long Text'), field('customer_text', 'Long Text'), field('state', 'Select', 'pending\ncompleted\nfailed'), field('error_message', 'Small Text')],
    'AI Operation': [link('attempt', 'AI Attempt'), field('operation_key', unique=1), field('request_id'), field('operation'), field('fingerprint'), field('response_json', 'Long Text')],
    'AI Provider Settings': [field('api_key', 'Password'), field('text_model', default='openai/gpt-oss-120b'), field('stt_model', default='whisper-large-v3-turbo'), field('tts_model', default='canopylabs/orpheus-v1-english'), field('tts_voice', default='troy')],
    'BPO Import Record': [field('source_id', unique=1), field('source_hash'), field('target_doctype'), field('target_name')],
    'BPO Reminder': [field('reminder_key', unique=1), link('assignment', 'BPO Training Assignment'), link('member', 'User'), field('category'), field('local_date', 'Date')],
}

schemas['AI Attempt'].append(field('activity_id'))

if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT.parent / '__init__.py').touch()
    (ROOT / '__init__.py').touch()
    for name, fields in schemas.items():
        slug = name.lower().replace(' ', '_')
        path = ROOT / slug
        path.mkdir(exist_ok=True)
        (path / '__init__.py').touch()
        admin = dict(role='BPO Administrator', read=1, report=1, export=1, print=1)
        if name in {'BPO Client', 'BPO Process', 'BPO Process Access', 'AI Provider Settings'}:
            admin.update(create=1, write=1, delete=1)
        definition = dict(doctype='DocType', name=name, module='BPO Coach', autoname='hash', engine='InnoDB',
                          field_order=[f['fieldname'] for f in fields], fields=fields, permissions=[admin],
                          track_changes=1, allow_rename=0)
        if name == 'AI Provider Settings':
            definition['issingle'] = 1
        (path / (slug + '.json')).write_text(json.dumps(definition, indent=2) + '\n', encoding='utf-8')
        cls = name.replace(' ', '')
        (path / (slug + '.py')).write_text(f'from bpo_coach.records import BPORecord\n\n\nclass {cls}(BPORecord):\n    pass\n', encoding='utf-8')
