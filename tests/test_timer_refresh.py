"""Displayed seconds must follow the ledger, regardless of old fraction phase."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class TimerRefreshTests(unittest.TestCase):
    def test_real_widget_tracks_ledger_every_second_with_fraction_mismatch(self):
        probe=r'''
import os
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QSignalSpy,QTest
from PyQt6.QtCore import QTimer
import time
app=QApplication([])
with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
    from core.config_manager import config_mgr
from core.interaction_fixes import install as install_interaction
install_interaction()
from core.timer_fixes import install,controller
install()
from core.timer_history import get_history_store
from core.window_tracker import WindowInfo
from core.activity_engine import activity_engine
from ui.timer_widget import TimerWidget
config_mgr.config['groups']={'work':['Editor']}
config_mgr.config['timers']=[dict(id='a',name='Work',group='work',idle_timeout=60,elapsed_seconds=0)]
config_mgr.config['pets']=[]
controller.history=get_history_store()
controller.foreground=lambda:WindowInfo(app_name='Editor',pid=os.getpid()+100,window_id=123)
controller.idle=lambda:0
controller.allowed=lambda:True
mono=[0.0];wall=[1_800_000_000.0]
controller.clock=lambda:mono[0];controller.wall_clock=lambda:wall[0]
timer=TimerWidget(config_mgr.config['timers'][0],lambda:[timer],lambda ident:None,lambda:None)
activity_engine.tick.connect(lambda updates:timer.update_time(updates['a']) if 'a' in updates else None)
spy=QSignalSpy(activity_engine.tick)
controller.step()
# Old frontend fraction phase can differ from ledger after resets/rounding.
controller.session.fractions['a']=0.95
last=0;changes=[]
for step in range(1,61):
    mono[0]=step/5;wall[0]=1_800_000_000.0+mono[0]
    controller.step();app.processEvents()
    expected=controller.history.display_seconds('a')
    assert config_mgr.config['timers'][0]['elapsed_seconds']==expected,(step,'config',expected,config_mgr.config['timers'][0])
    assert timer.label_time.text()==f'00:00:{expected:02}',(step,'label',timer.label_time.text(),expected)
    if expected!=last:
        changes.append(step);last=expected
assert last>=11 and len(changes)>=11,changes
assert all(b-a<=6 for a,b in zip(changes,changes[1:])),changes
# Single reset preserves history and continues publishing at each second.
activity_engine.running=True;activity_engine.before_reset=controller.prepare_reset
activity_engine.reset_timers(['a'])
assert timer.label_time.text()=='00:00:00'
for step in range(61,76):
    mono[0]=step/5;wall[0]=1_800_000_000.0+mono[0]
    controller.step();app.processEvents()
    expected=controller.history.display_seconds('a')
    assert timer.label_time.text()==f'00:00:{expected:02}'
assert expected>=2
# Pausing must freeze both ledger and display; resuming does not backfill.
config_mgr.config['timers'][0]['paused']=True
mono[0]+=.2;wall[0]+=.2;controller.step()
frozen=controller.history.display_seconds('a')
for _ in range(6):
    mono[0]+=.2;wall[0]+=.2;controller.step()
assert controller.history.display_seconds('a')==frozen
# Exercise the real Qt event loop too, rather than only synthetic steps.
config_mgr.config['timers'][0]['paused']=False
controller.clock=time.monotonic;controller.wall_clock=time.time
controller.session.last_step=None;controller.last_wall=None
emissions=[]
activity_engine.tick.connect(lambda updates:emissions.append(time.monotonic()) if 'a' in updates else None)
poll=QTimer();poll.timeout.connect(controller.step);poll.start(200)
QTest.qWait(5600);poll.stop()
assert len(emissions)>=4,emissions
assert all(b-a<1.6 for a,b in zip(emissions,emissions[1:])),emissions
controller.stop();timer.close()
print('PASS: every ledger second reaches the actual label; resets and pauses preserve accounting')
'''
        with tempfile.TemporaryDirectory(prefix='compet-refresh-test-') as profile:
            env=os.environ.copy();env.update(COMPET_TEST_PROFILE=profile,PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'),QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'))
            result=subprocess.run([sys.executable,'-c',probe],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
