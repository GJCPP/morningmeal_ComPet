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

    def test_manual_idle_exemption_keeps_other_gates_and_sleep_accounting(self):
        from core.timer_policy import TimerSession
        for duration in (15,30,60,None):
            with self.subTest(duration=duration):
                registry=ManualOverrides()
                registry.assign('app:video','video',duration,100,0)
                data={'groups':{'video':['Video']},'timers':[
                    dict(id='video',group='video',idle_timeout=5,elapsed_seconds=0)]}
                session=TimerSession()
                selected=registry.get('app:video',{'video'},100,0).timer_id
                session.step(data,['Video'],'',float('inf'),0,override_timer_id=selected)
                self.assertEqual(session.step(data,['Video'],'',float('inf'),1,override_timer_id=selected),{'video':1})
                self.assertEqual(session.reason,'counting')
                self.assertEqual(session.step(data,['Video'],'',1000,100,override_timer_id=selected),{})
                self.assertEqual(session.step(data,['Video'],'',1000,101,override_timer_id=selected),{'video':2})
                data['timers'][0]['paused']=True
                session.step(data,['Video'],'',1000,102,override_timer_id=selected)
                self.assertEqual(session.reason,'paused')
                data['timers'][0]['paused']=False
                session.step(data,['Video'],'',1000,103,allowed=False,override_timer_id=selected)
                self.assertEqual(session.reason,'permission')
                session.step(data,[],'',1000,104,override_timer_id=selected)
                self.assertFalse(session.counting_ids)
                session.step(data,['Video'],'',1000,105,available=False,override_timer_id=selected)
                self.assertEqual(session.reason,'unavailable')
                session.step(data,['Video'],'',1000,106,override_timer_id='deleted')
                self.assertEqual(session.reason,'idle')
                self.assertIsNone(session.override_timer_id)
                self.assertEqual(data['timers'][0]['idle_timeout'],5)

    def test_actual_menu_engine_display_cancel_history_and_other_app(self):
        code=r'''
import os,copy
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
app=QApplication([])
# The Windows offscreen plugin has no system font database by default.
if os.name == 'nt':
 from PyQt6.QtGui import QFontDatabase,QFont
 for font in ('segoeui.ttf','msyh.ttc','malgun.ttf','consola.ttf'):
  QFontDatabase.addApplicationFont(os.path.join(os.environ['SystemRoot'],'Fonts',font))
 QFont.insertSubstitution('monospace','Consolas')
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
assert widgets[0].override_cancel_button.isVisible() and '临时' in widgets[0].label_status.text()
label=widgets[0].label_status
assert widgets[0].width()==140 and widgets[0].height()==72
assert '\n' not in label.text()
# Watching without input must keep the explicitly selected timer counting.
idle[0]=10000
before=config_mgr.config['timers'][0]['elapsed_seconds']
step();step()
assert config_mgr.config['timers'][0]['elapsed_seconds']==before+2
assert controller.session.reason=='counting' and controller.is_active('work')
assert controller.session.counting_ids=={'work'}
# Other applications retain their automatic idle gating.
front[0]=WindowInfo(app_name='WeChat',pid=os.getpid()+20)
before=config_mgr.config['timers'][2]['elapsed_seconds']
step();step()
assert controller.session.reason=='idle' and not controller.is_active('chat')
assert config_mgr.config['timers'][2]['elapsed_seconds']==before
front[0]=WindowInfo(app_name='Safari',pid=os.getpid()+10);step();step()
assert controller.session.reason=='counting'
# Pausing and permission still gate accounting during manual assignment.
for kind in ('paused','permission'):
 before=[t['elapsed_seconds'] for t in config_mgr.config['timers']]
 if kind=='paused':config_mgr.config['timers'][0]['paused']=True
 if kind=='permission':allowed[0]=False
 step();step();assert [t['elapsed_seconds'] for t in config_mgr.config['timers']]==before
 config_mgr.config['timers'][0]['paused']=False;allowed[0]=True
 step()
idle[0]=0
front[0]=WindowInfo(app_name='WeChat',pid=os.getpid()+20);step();step()
assert controller.session.matched_ids==['chat']
front[0]=WindowInfo(app_name='Safari',pid=os.getpid()+10);step();step()
assert controller.session.matched_ids==['work']
idle[0]=10000
QTest.mouseClick(widgets[0].override_cancel_button,__import__('PyQt6.QtCore',fromlist=['Qt']).Qt.MouseButton.LeftButton)
before=[t['elapsed_seconds'] for t in config_mgr.config['timers']]
step();step();assert controller.session.matched_ids==['work','browse']
assert controller.session.reason=='idle' and not controller.is_active('work')
assert [t['elapsed_seconds'] for t in config_mgr.config['timers']]==before
# Until-cancel and custom duration menu actions are present and correctly wired.
menu=build_override_menu()
submenu=next(a.menu() for a in menu.actions() if a.menu() and any(x.data()==('browse',15) for x in a.menu().actions()))
next(a for a in submenu.actions() if a.data()==('browse',15)).trigger();step()
assert controller.session.matched_ids==['browse'] and controller.session.reason=='counting'
mono[0]+=901;wall[0]+=901;controller.step()
assert controller.session.matched_ids==['work','browse'] and controller.session.reason=='idle'
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
print('PASS: scoped override, real menus, popup focus, exclusive counting, manual idle exemption, pause/permission, automatic idle restoration, cancellation and history')
'''
        with tempfile.TemporaryDirectory(prefix='compet-override-test-') as profile:
            env=os.environ.copy();env.update(PYTHONUTF8='1',COMPET_TEST_PROFILE=profile,PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'),QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'))
            result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_card_footprint_stays_fixed_across_override_states_and_languages(self):
        code=r'''
import os
from unittest.mock import patch
from PyQt6.QtCore import Qt,QSize,QPoint
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
app=QApplication([])
# The Windows offscreen plugin has no system font database by default.
if os.name == 'nt':
 from PyQt6.QtGui import QFontDatabase,QFont
 for font in ('segoeui.ttf','msyh.ttc','malgun.ttf','consola.ttf'):
  QFontDatabase.addApplicationFont(os.path.join(os.environ['SystemRoot'],'Fonts',font))
 QFont.insertSubstitution('monospace','Consolas')
with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
 from core.config_manager import config_mgr
from core.interaction_fixes import install as interaction
interaction()
from core.timer_fixes import install,controller,_REASONS
install()
from core.i18n import I18n
from ui.timer_widget import TimerWidget
from ui.override_menu import compact_timer_status
long_name='LongTimer计时器\n' * 30
config_mgr.config['timers']=[dict(id='work',name=long_name,elapsed_seconds=61)]
config_mgr.config['pets']=[]
controller.clock=lambda:100
controller.wall_clock=lambda:1800000000
controller.session.display_id='work'
controller.session.reason='counting'
controller.presented_override_key='app:test'
card=TimerWidget(config_mgr.config['timers'][0],lambda:[],lambda _:None,lambda:None)
card.move(200,300)
controller.refresh_widgets()
app.processEvents()
position=QPoint(card.pos())
status_geometry=card.label_status.geometry()

def check_card():
 for _ in range(2):app.processEvents()
 assert card.size()==QSize(140,72),card.size()
 assert card.pos()==position,(card.pos(),position)
 assert card.label_name.toolTip()==long_name
 assert card.label_name.text()!=long_name
 for label in (card.label_name,card.label_time,card.label_status):
  assert label.text() and '\n' not in label.text(),repr(label.text())
  assert card.rect().contains(label.geometry()),label.geometry()
  # Text is centered on the whole card, including when the cancel button
  # consumes space. A centered QLabel inside an asymmetric row is not enough.
  bounds=label.geometry()
  assert abs(bounds.x()+bounds.width()/2-card.width()/2)<=0.5,(lang,label.text(),bounds)
  assert label.alignment()==Qt.AlignmentFlag.AlignCenter
  assert label.height()>=label.fontMetrics().height(),(lang,label.text(),label.height(),label.fontMetrics().height(),card.layout().minimumSize())
  assert label.fontMetrics().horizontalAdvance(label.text())<=label.contentsRect().width()+1
 current=card.label_status.geometry()
 assert (current.x(),current.width())==(status_geometry.x(),status_geometry.width())
 assert abs(current.y()+current.height()/2-status_geometry.y()-status_geometry.height()/2)<=0.5
 if card.override_cancel_button.isVisible():
  assert card.rect().contains(card.override_cancel_button.geometry())
  assert not card.label_status.geometry().intersects(card.override_cancel_button.geometry())
 assert card.label_time.text()=='10000:59:59',card.label_time.text()

for lang in ('zh_CN','zh_TW','en','ja','ko'):
 I18n.set_language(lang)
 for dark in (False,True):
  config_mgr.config['settings']['dark_mode']=dark
  card.update_metadata()
  card.update_time(10000*3600+59*60+59)
  controller.refresh_widgets();check_card()
  for minutes in (15,30,60,None):
   controller.overrides.assign('app:test','work',minutes,1800000000,100)
   for reason in _REASONS:
    controller.session.reason=reason
    controller.refresh_widgets();check_card()
    assert card.override_cancel_button.isVisible()
    assert card.label_status.text()==compact_timer_status(reason,True,None if minutes is None else minutes*60),card.label_status.text()
   controller.session.reason='counting'
   controller.refresh_widgets()
   # The compact cancellation button remains wired to the displayed rule.
   QTest.mouseClick(card.override_cancel_button,Qt.MouseButton.LeftButton)
   controller.refresh_widgets();check_card()
   assert not card.override_cancel_button.isVisible()
   assert controller.override_entry('app:test') is None
  # Expiry restores the normal row without changing size or position.
  controller.overrides.assign('app:test','work',15,1799999000,-900)
  controller.refresh_widgets();check_card()
  assert not card.override_cancel_button.isVisible()
card.close()
print('PASS: fixed footprint, real cancellation, expiry, all states, five languages, themes and long labels')
'''
        for scale in ('1','1.5','2'):
            with self.subTest(scale=scale), tempfile.TemporaryDirectory(prefix='compet-fixed-card-') as profile:
                env=os.environ.copy();env.update(PYTHONUTF8='1',COMPET_TEST_PROFILE=profile,
                    PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'),QT_SCALE_FACTOR=scale,
                    QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'))
                result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
