import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'morningmeal_Compet_V3'))
from core.timer_history import HistoryStore, statistics_day, period_bounds, split_interval


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='compet-history-test-')
        self.path=Path(self.temp.name)/'history.sqlite3'
        self.timers=[dict(id='a',name='Work',elapsed_seconds=123),dict(id='b',name='Study',elapsed_seconds=0)]
        self.store=HistoryStore(self.path,self.timers)
        self.tz=ZoneInfo('Asia/Shanghai')
        self.end=datetime(2026,11,3,7,tzinfo=self.tz).timestamp()
    def tearDown(self):self.store.close();self.temp.cleanup()
    def total(self,day=date(2026,11,3),period='day'):
        return self.store.distribution(day,period)[1]
    def test_migration_preserves_display_without_fabricating_history(self):
        self.assertEqual(self.store.display_seconds('a'),123)
        self.assertEqual(self.total(),0)
    def test_six_am_split_and_display_is_not_reset(self):
        end=datetime(2026,11,3,6,0,1,tzinfo=self.tz).timestamp()
        self.store.record({'a':2},end,self.tz)
        self.assertEqual(self.total(date(2026,11,2)),1)
        self.assertEqual(self.total(),1)
        self.assertEqual(self.store.display_seconds('a'),125)
    def test_single_all_reset_fractional_history_and_restart(self):
        self.store.record({'a':0.6,'b':0.6},self.end,self.tz)
        self.store.reset_display(['a'])
        self.store.record({'a':0.6,'b':0.6},self.end+0.6,self.tz)
        self.assertEqual(self.total(),2)
        self.assertEqual(self.store.display_seconds('a'),0)
        self.assertEqual(self.store.display_seconds('b'),1)
        self.store.reset_display(['a','b'])
        self.assertEqual(self.total(),2)
        self.store.record({'a':1,'b':1},self.end+1.6,self.tz)
        self.store.flush()
        second=HistoryStore(self.path,self.timers)
        self.assertEqual(second.display_seconds('a'),1)
        self.assertEqual(second.distribution(date(2026,11,3),'day')[1],4)
        second.close()
    def test_delete_rename_and_recreate_are_independent(self):
        self.store.record({'a':3},self.end,self.tz)
        self.timers[0]['name']='Renamed'
        self.store.sync_timers(self.timers)
        self.store.sync_timers([self.timers[1]])
        self.store.sync_timers([self.timers[1],dict(id='c',name='Renamed')])
        rows,_=self.store.distribution(date(2026,11,3),'day')
        archived=next(row for row in rows if row['id']=='a')
        self.assertTrue(archived['deleted']);self.assertEqual(archived['name'],'Renamed')
        self.assertEqual(archived['seconds'],3)
        self.assertEqual(self.store.display_seconds('c'),0)
    def test_calendar_periods_and_six_am_assignment(self):
        self.assertEqual(period_bounds(date(2026,11,3),'week'),(date(2026,11,2),date(2026,11,9)))
        self.assertEqual(period_bounds(date(2024,2,29),'month'),(date(2024,2,1),date(2024,3,1)))
        ts=datetime(2026,11,1,5,59,tzinfo=self.tz).timestamp()
        self.assertEqual(statistics_day(ts,self.tz),date(2026,10,31))
    def test_time_zone_changes_do_not_rewrite_prior_rows(self):
        self.store.record({'a':2},self.end,self.tz)
        self.store.record({'a':3},self.end,ZoneInfo('America/Los_Angeles'))
        self.assertEqual(self.total(),2)
        self.assertEqual(self.total(date(2026,11,2)),3)
    def test_dst_days_are_23_and_25_hours(self):
        tz=ZoneInfo('America/New_York')
        for begin,end,seconds in [((2026,3,7),(2026,3,8),23*3600),((2026,10,31),(2026,11,1),25*3600)]:
            a=datetime(*begin,6,tzinfo=tz).timestamp();b=datetime(*end,6,tzinfo=tz).timestamp()
            self.assertEqual(b-a,seconds)
            self.assertEqual(sum(value for _,value in split_interval(b,b-a,tz)),seconds*1_000_000)
            self.assertEqual(list(split_interval(b,b-a,tz))[0][0],date(*begin).isoformat())
    def test_flush_is_idempotent_and_rolls_back_on_failure(self):
        self.store.record({'a':2},self.end,self.tz)
        self.store.db.execute("CREATE TRIGGER deny_daily BEFORE INSERT ON daily BEGIN SELECT RAISE(FAIL,'test'); END")
        with self.assertRaises(Exception):self.store.flush()
        self.assertTrue(self.store.pending)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM daily').fetchone()[0],0)
        self.store.db.execute('DROP TRIGGER deny_daily')
        self.store.flush();self.store.flush()
        self.assertEqual(self.total(),2)


class HistoryQtTests(unittest.TestCase):
    def test_engine_reset_history_chart_and_clock_sleep_boundaries(self):
        code=r'''
import os
from datetime import date,datetime
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QDate
app=QApplication([])
with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
    from core.config_manager import config_mgr
from core.timer_fixes import install,controller
install()
from core.timer_history import get_history_store,statistics_day
from core.activity_engine import activity_engine
from core.window_tracker import WindowInfo
config_mgr.config['groups']={'shared':['Editor']}
config_mgr.config['timers']=[dict(id='a',name='Work',group='shared',elapsed_seconds=10,idle_timeout=60),dict(id='b',name='Study',group='shared',elapsed_seconds=0,idle_timeout=60)]
controller.history=get_history_store()
controller.foreground=lambda:WindowInfo(app_name='Editor',pid=os.getpid()+1,window_id=123)
controller.idle=lambda:0
controller.allowed=lambda:True
mono=[0]; wall=[datetime(2026,11,3,5,59,59).timestamp()]
controller.clock=lambda:mono[0];controller.wall_clock=lambda:wall[0]
activity_engine.running=True
activity_engine.before_reset=controller.prepare_reset
controller.step()
mono[0]+=2;wall[0]+=2;controller.step()
history=controller.history
assert history.distribution(date(2026,11,2),'day')[1]==2
assert history.distribution(date(2026,11,3),'day')[1]==2
activity_engine.reset_timers()
assert all(t['elapsed_seconds']==0 for t in config_mgr.config['timers'])
mono[0]+=1;wall[0]+=1;controller.step()
assert all(t['elapsed_seconds']==1 for t in config_mgr.config['timers'])
assert history.distribution(date(2026,11,3),'day')[1]==4
# A sleep gap and a wall-clock jump must not create time.
mono[0]+=100;wall[0]+=100;controller.step()
mono[0]+=1;wall[0]+=10000;controller.step()
assert history.distribution(date(2026,11,3),'day')[1]==4
from ui.timer_statistics import TimerStatisticsDialog
window=TimerStatisticsDialog();window.show();app.processEvents()
window.period_combo.setCurrentIndex(1)
window.date_edit.setDate(QDate(2026,11,3));window.refresh()
assert window.chart.total==4
activity_engine.reset_timers(['a'])
window.refresh();assert window.chart.total==4
window.period_combo.setCurrentIndex(2);window.refresh();assert window.chart.total==6
window.period_combo.setCurrentIndex(3);window.refresh();assert window.chart.total==6
window.period_combo.setCurrentIndex(0);window.refresh()
assert window.chart.total==1
assert not window.date_edit.isEnabled()
window.period_combo.setCurrentIndex(1)
window.go_today();assert window.date_edit.date().toString('yyyy-MM-dd')==statistics_day().isoformat()
window.close();controller.stop()
print('PASS: daily split, display reset, overlap, historical views, sleep and clock jump')
'''
        with tempfile.TemporaryDirectory(prefix='compet-history-qt-') as profile:
            env=os.environ.copy();env.update(COMPET_TEST_PROFILE=profile,QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'),PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'))
            result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
