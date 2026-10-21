"""Pure rules shared by HTTP execution, background grading and migration tests."""
from copy import deepcopy
import math
import re
import unicodedata

MODES = {'walkthrough', 'practice', 'assessment'}
CHANNELS = {'workflow', 'chat', 'voice'}

def js_round(value):
    return math.floor(value + 0.5)

def normalize_answer(value):
    # ECMAScript trim/\s includes BOM and excludes Python-only control whitespace.
    whitespace = r'[\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+'
    return re.sub(whitespace, ' ', unicodedata.normalize('NFKC', value)).strip(' ').lower()

def validate_action(scenario, step_index, hotspot_id, value=''):
    step = scenario['steps'][step_index] if 0 <= step_index < len(scenario['steps']) else {}
    hotspot = next((h for h in step.get('hotspots', []) if h['id'] == hotspot_id), None)
    normalized = normalize_answer(value)
    correct = bool(hotspot and hotspot['correct'] and (
        hotspot['type'] == 'click' or normalized and any(normalize_answer(a) == normalized for a in hotspot['accepted'])))
    return {'correct': correct, 'critical': bool(not correct and hotspot and hotspot['critical']), 'hotspot': hotspot}

def completed_step(scenario, index, events):
    if not 0 <= index < len(scenario['steps']):
        return False
    step = scenario['steps'][index]
    return all(any(e['step_id'] == step['id'] and e['hotspot_id'] == h['id'] and e['correct'] for e in events)
               for h in step['hotspots'] if h['correct'])

def objective_results(scenario, events):
    required = [(step, h) for step in scenario['steps'] for h in step['hotspots'] if h['correct']]
    completed = [(step, h) for step, h in required if any(
        e['step_id'] == step['id'] and e['hotspot_id'] == h['id'] and e['correct'] for e in events)]
    wrong = [e for e in events if not e['correct']]
    procedure = js_round(100 * len(completed) / (len(required) + len(wrong))) if required else 0
    resolution = 100 if required and len(completed) == len(required) else 0
    critical_steps = [step for step in scenario['steps'] if step['critical']]
    critical_passed = not any(e['critical'] for e in events) and all(
        any(e['step_id'] == step['id'] and e['hotspot_id'] == h['id'] and e['correct'] for e in events)
        for step in critical_steps for h in step['hotspots'] if h['correct'])
    return [
        {'key': 'procedure', 'score': procedure,
         'feedback': f'{len(completed)} of {len(required)} required actions completed; {len(wrong)} incorrect actions recorded.',
         'evidenceIds': [e['id'] for e in events]},
        {'key': 'resolution', 'score': resolution,
         'feedback': 'The expected work-item outcome was reached.' if resolution else 'The procedure was submitted with unfinished actions.',
         'evidenceIds': [e['id'] for step, h in completed for e in events if e['step_id'] == step['id'] and e['hotspot_id'] == h['id'] and e['correct']]},
        {'key': 'compliance', 'score': 100 if critical_passed else 0,
         'feedback': 'All critical procedural checks passed.' if critical_passed else 'A critical action failed or a required critical step was missed.',
         'evidenceIds': [e['id'] for e in events if e['critical'] or any(step['id'] == e['step_id'] for step in critical_steps)]},
    ]

def aggregate_assessment(scenario, criteria, started_at, now, strengths, improvements):
    total = sum(r['weight'] for r in scenario['rubric'])
    if total <= 0:
        raise ValueError('Rubric weights must be positive')
    score = js_round(sum(next((c['score'] for c in criteria if c['key'] == r['key']), 0) * r['weight']
                         for r in scenario['rubric']) / total)
    critical = next((c['score'] for c in criteria if c['key'] == 'compliance'), 0) == 100
    return dict(score=score, passed=score >= scenario['threshold'] and critical, criticalPassed=critical,
                criteria=criteria, strengths=strengths, improvements=improvements,
                elapsedSeconds=max(0, js_round((now - started_at) / 1000)))

def validate_evidence(criteria, events, turns):
    ids = {e['id'] for e in events} | {t['id'] for t in turns if t['state'] == 'completed'}
    return all(isinstance(c.get('score'), (int, float)) and not isinstance(c['score'], bool)
               and math.isfinite(c['score']) and 0 <= c['score'] <= 100
               and isinstance(c.get('evidenceIds'), list) and (c['score'] == 0 or c['evidenceIds'])
               and all(e in ids for e in c['evidenceIds']) for c in criteria)

def sanitize_scenario(scenario, mode, version):
    result = {key: scenario[key] for key in ('title', 'office', 'brief', 'customerName')}
    result.update(version=version, steps=[])
    for i, step in enumerate(scenario['steps']):
        item = dict(id=step['id'], assetId=step['assetId'], hotspots=[])
        item.update({key: step[key] for key in ('title', 'instructions', 'hint')} if mode != 'assessment' else {'title': f'Screen {i + 1}'})
        for h in step['hotspots']:
            region = {key: h[key] for key in ('id', 'label', 'type', 'x', 'y', 'w', 'h')}
            if mode == 'walkthrough':
                region['correct'] = h['correct']
            item['hotspots'].append(region)
        result['steps'].append(item)
    return result

def approved_channels(channels, attempts):
    return [c for c in channels if any(a['channel'] == c and a['mode'] == 'assessment' and a['status'] == 'approved' for a in attempts)]

def publish_problems(s):
    errors = []
    if not all(s[k].strip() for k in ('brief', 'reference', 'outcome')):
        errors.append('Add a brief, reference instructions and expected outcome.')
    if not s['steps']:
        errors.append('Add at least one screenshot step.')
    for i, step in enumerate(s['steps']):
        if not all(step[k].strip() for k in ('assetId', 'title', 'instructions')):
            errors.append(f'Step {i + 1} needs a screenshot, title and instructions.')
        if not any(h['correct'] for h in step['hotspots']):
            errors.append(f'Step {i + 1} needs a correct action.')
        if any(h['correct'] and h['type'] == 'input' and not any(a.strip() for a in h['accepted']) for h in step['hotspots']):
            errors.append(f'Step {i + 1} needs accepted input answers.')
    required = {'procedure', 'resolution', 'compliance'} | ({'communication'} if s['office'] == 'front' else set())
    if required - {r['key'] for r in s['rubric']}:
        errors.append('Include all required rubric categories.')
    if s['office'] == 'front' and not all(s[k].strip() for k in ('persona', 'opening', 'customerName')):
        errors.append('Add a customer name, persona and opening message.')
    return errors

def first_attempt_metrics(attempts):
    first = {}
    candidates = [a for a in attempts if a['mode'] == 'assessment' and a.get('grading_status') == 'completed']
    for a in sorted(candidates, key=lambda a: (str(a.get('submitted_at') or ''), a['name'])):
        key = (a['member'], a['assignment'], a.get('lesson') or '', a.get('activity_id') or '', a['scenario_version'], a['channel'])
        first.setdefault(key, a)
    passed = sum(bool(a.get('result', {}).get('passed')) for a in first.values())
    return {'first_attempts': len(first), 'first_attempt_passes': passed,
            'first_attempt_pass_rate': 100 * passed / len(first) if first else None}
