import json
from pathlib import Path
import unittest


class SchemaCompatibility(unittest.TestCase):
    def test_scopes_do_not_shadow_the_pinned_meta_process_method(self):
        directory = Path(__file__).parents[1] / 'bpo_coach/bpo_coach/doctype'
        scoped = 0
        for path in directory.glob('*/*.json'):
            definition = json.loads(path.read_text(encoding='utf-8'))
            for field in definition['fields']:
                self.assertNotEqual(field['fieldname'], 'process', path)
                if field.get('options') == 'BPO Process':
                    self.assertEqual(field['fieldname'], 'bpo_process', path)
                    scoped += 1
        self.assertEqual(scoped, 6)
