import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch


class PeopleCsv(unittest.TestCase):
    def setUp(self):
        frappe = MagicMock()
        frappe.whitelist.side_effect = lambda: lambda fn: fn
        rate = MagicMock()
        rate.rate_limit.side_effect = lambda **kwargs: lambda fn: fn
        modules = {'frappe': frappe, 'frappe.rate_limiter': rate, 'bpo_coach.security': MagicMock()}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('people_csv_under_test', Path(__file__).parents[1] / 'bpo_coach/people_import.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    def test_spreadsheet_quoting_bom_multiline_and_password_whitespace(self):
        rows = self.module.parse_people_csv('\ufeffname,email,password\r\n"Smith, ""Jo""\nDoe", JO@example.test ," secret123456 "\r\n')
        self.assertEqual(rows, [{'row': 2, 'name': 'Smith, "Jo"\nDoe', 'email': 'jo@example.test',
                                'password': ' secret123456 ', 'role': '', 'batchids': ''}])

    def test_invalid_structure_and_limits(self):
        for source in ('', 'name,email\n', 'name,email\n"Unclosed,test',
                       'name,email\nName,test,extra', 'name,email,email\nName,test,test',
                       'name,unknown\nName,test', 'name,email\n' + 'Name,test\n' * 101,
                       'x' * 500_001):
            with self.subTest(source=source[:50]), self.assertRaises(self.module.RowError):
                self.module.parse_people_csv(source)

    def test_blank_lines_and_physical_row_numbers(self):
        rows = self.module.parse_people_csv('\nname,email\n\nOne,one@example.test\nTwo,two@example.test\n')
        self.assertEqual([row['row'] for row in rows], [4, 5])
