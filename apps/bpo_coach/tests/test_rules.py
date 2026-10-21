import copy
import json
from pathlib import Path
import unittest
from bpo_coach import engine
from bpo_coach.validation import validate_scenario

FIXTURE = json.loads((Path(__file__).parent / 'parity.json').read_text(encoding='utf-8'))

class PilotParity(unittest.TestCase):
    def test_scoring_fixtures(self):
        for i, c in enumerate(FIXTURE['cases']):
            with self.subTest(case=i):
                self.assertEqual(engine.objective_results(c['scenario'], c['events']), c['objective'])
                self.assertEqual(engine.completed_step(c['scenario'], 0, c['events']), c['completed'])
                self.assertEqual(engine.aggregate_assessment(c['scenario'], c['criteria'], 1000, 2500, [], []), c['assessment'])
                self.assertEqual(bool(engine.validate_evidence(c['criteria'], c['events'], [])), c['validEvidence'])

    def test_normalization(self):
        for c in FIXTURE['normalization']:
            self.assertEqual(engine.normalize_answer(c['value']), c['expected'])

    def test_actions(self):
        for c in FIXTURE['actions']:
            self.assertEqual(engine.validate_action(FIXTURE['scenario'], 0, 'input', c['value']), c['result'])

    def test_assessment_redaction(self):
        for c in FIXTURE['redaction']:
            self.assertEqual(engine.sanitize_scenario(FIXTURE['scenario'], c['mode'], 3), c['result'])
        redacted = json.dumps(engine.sanitize_scenario(FIXTURE['scenario'], 'assessment', 3))
        for secret in ('INV-1048', 'Do not pay', 'accepted', 'critical', 'correct', 'hint'):
            self.assertNotIn(secret, redacted)

    def test_python_rounding_matches_javascript(self):
        self.assertEqual(engine.js_round(12.5), 13)

    def test_unknown_evidence_is_rejected(self):
        self.assertFalse(engine.validate_evidence([{'score':100,'evidenceIds':['invented']}],[],[]))
        self.assertFalse(engine.validate_evidence([{'score':float('nan'),'evidenceIds':[]}],[],[]))

    def test_practice_never_completes_a_channel(self):
        self.assertEqual(engine.approved_channels(['voice'],[{'channel':'voice','mode':'practice','status':'approved'}]),[])

    def test_metric_excludes_failed_processing_and_practice(self):
        def attempt(name,mode,status,score,time,channel='chat'):
            return dict(name=name,member='learner',assignment='assignment',scenario_version='v1',channel=channel,
                mode=mode,grading_status=status,result={'passed':score},submitted_at=time)
        result=engine.first_attempt_metrics([
            attempt('practice','practice','completed',True,'1'), attempt('failedjob','assessment','failed',True,'2'),
            attempt('first','assessment','completed',False,'3'), attempt('retry','assessment','completed',True,'4'),
            attempt('voice','assessment','completed',True,'5',channel='voice')])
        self.assertEqual(result,dict(first_attempts=2,first_attempt_passes=1,first_attempt_pass_rate=50))

    def test_scenario_validation_rejects_duplicate_actions_and_overflow(self):
        s=copy.deepcopy(FIXTURE['scenario'])
        validate_scenario(s,publishing=True)
        s['steps'][0]['hotspots'].append(s['steps'][0]['hotspots'][0])
        with self.assertRaises(ValueError): validate_scenario(s)
        s=copy.deepcopy(FIXTURE['scenario']);s['steps'][0]['hotspots'][0]['x']=.99
        with self.assertRaises(ValueError): validate_scenario(s)

if __name__=='__main__': unittest.main()
