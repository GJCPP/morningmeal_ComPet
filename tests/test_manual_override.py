"""Temporary assignment is app-scoped, permission-gated, and never persisted."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'morningmeal_Compet_V3'))
from core.manual_override import ManualOverrides,app_identity
from core.window_tracker import WindowInfo


class OverridePolicyTests(unittest.TestCase):
    def test_identity_expiry_suspend_clock_change_and_session_only(self):
        safari=WindowInfo(app_name='Safari',pid=1);safari.bundle_id='com.apple.Safari'
        self.assertEqual(app_identity(safari)[0],'bundle:com.apple.safari')
        self.assertEqual(app_identity(WindowInfo(app_name='chrome.exe'))[0],app_identity(WindowInfo(app_name='CHROME'))[0])
        registry=ManualOverrides();registry.assign('safari','work',30,100,10)
        self.assertEqual(registry.get('safari',{'work'},100,10).remaining(100,10),1800)
        self.assertIsNone(registry.get('wechat',{'work'},110,20))
        self.assertIsNotNone(registry.get('safari',{'work'},120,30))
        self.assertIsNone(registry.get('safari',{'work'},1900,40))  # sleep included
        registry.assign('safari','work',15,100,10)
        self.assertIsNone(registry.get('safari',{'work'},50,911))  # backwards wall clock cannot extend it
        registry.assign('safari','work',None,100,10)
        self.assertIsNotNone(registry.get('safari',{'work'},1e9,1e9))
        self.assertIsNone(ManualOverrides().get('safari',{'work'},100,10))
        self.assertIsNone(registry.get('safari',set(),100,10))  # deleted target

    def test_actual_menu_engine_display_cancel_history_and_other_app(self):
        code=r'''
import os,copy
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
app=QApplication([])
with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
 from core.config_manager import config_mgr
from core.interaction_fixes import install as interaction
interaction()
from core.timer_fixes import install,controller
install()
from core.timer_history import get_history_store
from core.activity_engine import activity_engine
from core.window_tracker import WindowInfo
from ui.timer_widget import TimerWidget
from ui.mini_dialogs import TimerMiniDialog
from ui.override_menu import build_override_menu
from core.i18n import I18n
I18n.set_language('zh_CN')
config_mgr.config['groups']={'work':['Safari'],'browse':['Safari'],'chat':['WeChat']}
config_mgr.config['timers']=[dict(id=k,name=k,group=g,elapsed_seconds=0,idle_timeout=60) for k,g in [('work','work'),('browse','browse'),('chat','chat')]]
config_mgr.config['pets']=[]
controller.history=get_history_store()
mono=[0];wall=[1_800_000_000];front=[WindowInfo(app_name='Safari',pid=os.getpid()+10)]
controller.clock=lambda:mono[0];controller.wall_clock=lambda:wall[0];controller.foreground=lambda:front[0]
idle=[0];allowed=[True];controller.idle=lambda:idle[0];controller.allowed=lambda:allowed[0]
widgets=[]
for data in config_mgr.config['timers']:
 widget=TimerWidget(data,lambda:widgets,lambda tid:None,lambda:None);widgets.append(widget)
activity_engine.tick.connect(lambda updates:[w.update_time(updates[w.timer_data['id']]) for w in widgets if w.timer_data['id'] in updates])
def step(seconds=1):
 mono[0]+=seconds;wall[0]+=seconds;controller.step();app.processEvents()
controller.step();step()
assert [t['elapsed_seconds'] for t in config_mgr.config['timers']]==[1,1,0]
target=controller.override_target()
menu=build_override_menu()
# The menu captures Safari before the popup itself takes foreground focus.
front[0]=WindowInfo(app_name='ComPet',pid=os.getpid());step()
action=next(a for a in menu.actions() if a.data()==('work',30));action.trigger()
assert controller.override_entry(target[0]).remaining(wall[0],mono[0])==1800
front[0]=WindowInfo(app_name='Safari',pid=os.getpid()+10);step();step()
assert controller.session.matched_ids==['work']
assert config_mgr.config['timers'][1]['elapsed_seconds']==1
assert widgets[0].override_cancel_button.isVisible() and '临时指定' in widgets[0].label_status.text()
label=widgets[0].label_status
assert label.height()>=label.heightForWidth(label.width()),(label.height(),label.heightForWidth(label.width()))
# Pausing/idle/permission still gate accounting; overriding never bypasses them.
for kind in ('paused','idle','permission'):
 before=[t['elapsed_seconds'] for t in config_mgr.config['timers']]
 if kind=='paused':config_mgr.config['timers'][0]['paused']=True
 if kind=='idle':idle[0]=100
 if kind=='permission':allowed[0]=False
 step();step();assert [t['elapsed_seconds'] for t in config_mgr.config['timers']]==before
 config_mgr.config['timers'][0]['paused']=False;idle[0]=0;allowed[0]=True
 step()
front[0]=WindowInfo(app_name='WeChat',pid=os.getpid()+20);step();step()
assert controller.session.matched_ids==['chat']
front[0]=WindowInfo(app_name='Safari',pid=os.getpid()+10);step();step()
assert controller.session.matched_ids==['work']
QTest.mouseClick(widgets[0].override_cancel_button,__import__('PyQt6.QtCore',fromlist=['Qt']).Qt.MouseButton.LeftButton)
step();assert controller.session.matched_ids==['work','browse']
# Until-cancel and custom duration menu actions are present and correctly wired.
menu=build_override_menu()
submenu=next(a.menu() for a in menu.actions() if a.menu() and any(x.data()==('browse',15) for x in a.menu().actions()))
next(a for a in submenu.actions() if a.data()==('browse',15)).trigger();step()
assert controller.session.matched_ids==['browse']
mono[0]+=901;wall[0]+=901;controller.step()
assert controller.session.matched_ids==['work','browse']
# Deleted timers invalidate the override; failed foreground never accrues.
controller.assign_override(target,'work',None)
config_mgr.config['timers']=config_mgr.config['timers'][1:];step()
assert controller.override_entry(target[0]) is None
front[0]=WindowInfo();step();assert not controller.session.counting_ids
config_mgr.save_config()
from core.config_manager import CONFIG_PATH
assert 'bundle:' not in __import__('pathlib').Path(CONFIG_PATH).read_text()
controller.stop()
assert controller.history.distribution(None,'all')[1]>0
for widget in widgets:widget.close()
print('PASS: scoped override, real menus, popup focus, exclusive counting, pause/idle/permission, cancellation and history')
'''
        with tempfile.TemporaryDirectory(prefix='compet-override-test-') as profile:
            env=os.environ.copy();env.update(COMPET_TEST_PROFILE=profile,PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'),QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'))
            result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
