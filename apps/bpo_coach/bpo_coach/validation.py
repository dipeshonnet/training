import json
from pathlib import Path
from jsonschema import Draft202012Validator
from bpo_coach.engine import publish_problems

VALIDATOR = Draft202012Validator(json.loads((Path(__file__).parent / 'scenario.schema.json').read_text(encoding='utf-8')))

def validate_scenario(value, publishing=False):
    if not isinstance(value, dict):
        raise ValueError('Scenario must be an object.')
    errors = sorted(VALIDATOR.iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise ValueError('; '.join(e.message for e in errors[:5]))
    step_ids = [s['id'] for s in value['steps']]
    action_ids = [h['id'] for s in value['steps'] for h in s['hotspots']]
    keys = [r['key'] for r in value['rubric']]
    if len(step_ids) != len(set(step_ids)) or len(action_ids) != len(set(action_ids)) or len(keys) != len(set(keys)):
        raise ValueError('Step, hotspot and criterion identifiers must be unique.')
    if value['office'] == 'back' and 'communication' in keys:
        raise ValueError('Communication applies only to front-office scenarios.')
    if any(h['x'] + h['w'] > 1.001 or h['y'] + h['h'] > 1.001 for s in value['steps'] for h in s['hotspots']):
        raise ValueError('Region must fit within its screenshot.')
    if publishing and (problems := publish_problems(value)):
        raise ValueError(' '.join(problems))
    return value
