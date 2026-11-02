"""Default artwork migration must preserve custom skins and timer history."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'morningmeal_Compet_V3/core/config_manager.py'


class DefaultSkinTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(SOURCE.read_text())
        tree.body=[node for node in tree.body if not (isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='config_mgr' for t in node.targets))]
        self.ns={'__file__':str(SOURCE),'__name__':'skin_probe'}
        exec(compile(tree,str(SOURCE),'exec'),self.ns)
        self.temp=tempfile.TemporaryDirectory(prefix='compet-skin-test-')
        self.root=Path(self.temp.name)
        for name,value in {'USER_DATA_DIR':self.root,'SKINS_DIR':self.root/'skins',
                           'USER_SOUNDS_DIR':self.root/'sounds','CONFIG_PATH':self.root/'config.json'}.items():
            self.ns[name]=str(value)
        self.legacy=self.root/'skins/default'
        self.manager_type=self.ns['ConfigManager']
    def tearDown(self):self.temp.cleanup()
    def create_legacy(self,custom=False):
        self.legacy.mkdir(parents=True)
        self.ns['LEGACY_DEFAULT_IMAGES']={}
        for name in ('idle.png','tap_left.png','tap_right.png'):
            data=('original-'+name).encode()
            self.ns['LEGACY_DEFAULT_IMAGES'][name]=hashlib.sha256(data).hexdigest()
            (self.legacy/name).write_bytes(data)
        (self.legacy/'config.json').write_text(json.dumps({'key_mappings':{'q':'idle.png'} if custom else {}}))
    def test_fresh_profile_only_has_yi_and_valid_images(self):
        manager=self.manager_type()
        self.assertEqual(manager.config['pets'][0]['skin'],'羿')
        self.assertEqual([p.name for p in (self.root/'skins').iterdir()],['羿'])
        for name in ('idle.png','tap_left.png','tap_right.png'):
            self.assertGreater((self.root/'skins/羿'/name).stat().st_size,100)
    def test_original_is_retired_and_existing_counts_and_pet_settings_survive(self):
        self.create_legacy()
        data={'pets':[{'id':'p','skin':'default','scale':0.65,'x':23,'y':45}],
              'timers':[{'id':'t','elapsed_seconds':12345,'idle_timeout':60}], 'groups':{'work':['Editor']}}
        (self.root/'config.json').write_text(json.dumps(data))
        manager=self.manager_type()
        self.assertFalse(self.legacy.exists())
        self.assertEqual(len(list((self.root/'retired-skins').iterdir())),1)
        self.assertEqual(manager.config['pets'],[dict(data['pets'][0],skin='羿')])
        self.assertEqual(manager.config['timers'],data['timers'])
        self.assertEqual(manager.config['groups'],data['groups'])
        manager.save_config()
        again=self.manager_type()
        self.assertEqual(again.config['pets'],manager.config['pets'])
        self.assertEqual(len(list((self.root/'retired-skins').iterdir())),1)
    def test_custom_legacy_artwork_or_mappings_are_preserved(self):
        self.create_legacy(custom=True)
        self.manager_type()
        self.assertTrue(self.legacy.exists())
        (self.legacy/'config.json').write_text('{"key_mappings":{}}')
        (self.legacy/'idle.png').write_bytes(b'custom artwork')
        self.manager_type()
        self.assertTrue(self.legacy.exists())
    def test_existing_yi_is_not_overwritten(self):
        path=self.root/'skins/羿';path.mkdir(parents=True)
        (path/'config.json').write_text('{"name":"custom yi","squash_depth":0.75}')
        self.manager_type()
        self.assertEqual(json.loads((path/'config.json').read_text())['squash_depth'],0.75)
