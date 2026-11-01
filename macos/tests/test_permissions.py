import ast
from pathlib import Path
import unittest

SOURCE=Path(__file__).resolve().parents[2]/'morningmeal_Compet_V3/core/macos_compat.py'


class PermissionRequestTests(unittest.TestCase):
    def setup_request(self, allowed=False, result=False):
        calls=[]
        namespace={'_compet_permission_requested':False,
                   '_compet_listen_allowed':lambda:allowed,
                   '_compet_request_listen':lambda:calls.append('request') or result,
                   '_compet_ensure_native_input':lambda:calls.append('listen')}
        tree=ast.parse(SOURCE.read_text())
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_compet_request_input_permission')
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(SOURCE),'exec'),namespace)
        return namespace,calls

    def test_authorized_does_not_prompt(self):
        state,calls=self.setup_request(allowed=True)
        self.assertTrue(state['_compet_request_input_permission']())
        self.assertEqual(calls,['listen'])

    def test_denied_prompts_once_even_with_repeated_calls(self):
        state,calls=self.setup_request()
        self.assertFalse(state['_compet_request_input_permission']())
        self.assertFalse(state['_compet_request_input_permission']())
        self.assertEqual(calls,['request'])

    def test_grant_starts_listener(self):
        state,calls=self.setup_request(result=True)
        self.assertTrue(state['_compet_request_input_permission']())
        self.assertEqual(calls,['request','listen'])

    def test_manual_grant_is_detected_without_another_prompt(self):
        state,calls=self.setup_request()
        state['_compet_request_input_permission']()
        state['_compet_listen_allowed']=lambda:True
        self.assertTrue(state['_compet_request_input_permission']())
        self.assertEqual(calls,['request','listen'])

if __name__=='__main__':
    unittest.main()
