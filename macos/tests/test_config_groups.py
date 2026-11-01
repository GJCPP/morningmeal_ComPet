import ast
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'morningmeal_Compet_V3/core/config_manager.py'


class ConfigGroupTests(unittest.TestCase):
    def setUp(self):
        # Load the real config reader without constructing the application singleton.
        tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'config_mgr' for target in node.targets))]
        self.namespace = {'__file__': str(SOURCE), '__name__': 'config_reader_probe'}
        exec(compile(tree, str(SOURCE), 'exec'), self.namespace)
        self.temp = tempfile.TemporaryDirectory(prefix='compet-group-test-')
        self.path = Path(self.temp.name) / 'config.json'
        self.namespace['CONFIG_PATH'] = str(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def load(self, value=None):
        if value is not None:
            self.path.write_text(json.dumps(value))
        return self.namespace['ConfigManager'].load_config(None)

    def test_fresh_profile_has_no_automatic_group(self):
        result = self.load()
        self.assertEqual(result['groups'], {})
        self.assertEqual(result['timers'][0]['group'], '')

    def test_saved_groups_are_authoritative(self):
        result = self.load({'groups': {'工作': ['Logseq']}})
        self.assertEqual(result['groups'], {'工作': ['Logseq']})

    def test_explicit_empty_group_list_stays_empty(self):
        self.assertEqual(self.load({'groups': {}})['groups'], {})

    def test_save_reload_does_not_regenerate_deleted_group(self):
        first = self.load({'groups': {'工作': ['Logseq']}, 'timers': [{'id':'existing','group':'工作','elapsed_seconds':130}]})
        second = self.load(first)
        self.assertEqual(second['groups'], {'工作': ['Logseq']})
        self.assertEqual(second['timers'], first['timers'])
        self.assertEqual(second['timers'][0]['elapsed_seconds'], 130)

if __name__ == '__main__':
    unittest.main()
