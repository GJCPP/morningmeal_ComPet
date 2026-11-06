"""All-history statistics aggregate only recorded dates and survive display resets."""
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'morningmeal_Compet_V3'))
from core.timer_history import HistoryStore


class AllHistoryTests(unittest.TestCase):
    def test_all_dates_pending_flush_restart_reset_deleted_and_legacy(self):
        with tempfile.TemporaryDirectory(prefix='compet-all-history-') as directory:
            path=Path(directory)/'history.sqlite3'
            timers=[dict(id='a',name='Work',elapsed_seconds=9999),dict(id='b',name='Study',elapsed_seconds=0)]
            store=HistoryStore(path,timers)
            self.assertEqual(store.distribution(None,'all')[1],0)
            tz=ZoneInfo('Asia/Shanghai')
            end=datetime(2025,1,2,12,tzinfo=tz).timestamp()
            store.record({'a':60,'b':30},end,tz);store.flush()
            store.record({'a':60},datetime(2026,11,6,12,tzinfo=tz).timestamp(),tz)
            rows,total=store.distribution(None,'all')
            self.assertEqual(total,150)
            self.assertEqual([r['seconds'] for r in rows],[120,30])
            self.assertAlmostEqual(rows[0]['share'],.8)
            store.reset_display(['a','b'])
            self.assertEqual(store.distribution(None,'all')[1],150)
            store.sync_timers([dict(id='b',name='Renamed'),dict(id='c',name='Work',elapsed_seconds=0)])
            rows,total=store.distribution(None,'all')
            self.assertEqual(total,150)
            self.assertTrue(next(r for r in rows if r['id']=='a')['deleted'])
            self.assertEqual(next(r for r in rows if r['id']=='b')['name'],'Renamed')
            self.assertEqual(next(r for r in rows if r['id']=='c')['seconds'],0)
            store.flush();store.flush();self.assertEqual(store.distribution(None,'all')[1],150)
            store.close()
            store=HistoryStore(path,[dict(id='b',name='Renamed'),dict(id='c',name='Work')])
            self.assertEqual(store.distribution(None,'all')[1],150)
            store.close()

    def test_fractional_seconds_aggregate_across_days_before_rounding(self):
        with tempfile.TemporaryDirectory(prefix='compet-all-fractions-') as directory:
            store=HistoryStore(Path(directory)/'history.sqlite3',[dict(id='a',name='A')])
            for day in (1,2):
                store.record({'a':.6},datetime(2026,11,day,12).timestamp())
            self.assertEqual(store.distribution(None,'all')[1],1)
            store.close()

    def test_qt_all_history_switch_is_live_and_date_controls_disabled(self):
        code=r'''
import os
from datetime import datetime
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
app=QApplication([])
with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
 from core.config_manager import config_mgr
config_mgr.config['timers']=[dict(id='a',name='A',elapsed_seconds=5000)]
from core.timer_history import get_history_store
store=get_history_store();store.record({'a':30},datetime(2025,1,1,12).timestamp());store.flush()
store.record({'a':60},datetime(2026,11,6,12).timestamp())
from core.i18n import I18n
from ui.timer_statistics import TimerStatisticsDialog
window=TimerStatisticsDialog();window.show()
window.period_combo.setCurrentIndex(window.period_combo.findData('all'));app.processEvents()
assert window.chart.total==90
assert not window.date_edit.isEnabled() and not window.previous_button.isEnabled() and not window.today_button.isEnabled()
assert not window.note_label.isVisible()
for lang in ('zh_CN','en','zh_TW','ja','ko'):
 I18n.set_language(lang);app.processEvents();assert window.period_combo.currentText()!='all'
store.reset_display(['a']);window.refresh();assert window.chart.total==90
store.record({'a':3},datetime(2026,11,6,12).timestamp());QTest.qWait(1150)
assert window.chart.total==93
window.period_combo.setCurrentIndex(1);app.processEvents();assert window.date_edit.isEnabled()
window.period_combo.setCurrentIndex(4);app.processEvents();assert window.chart.total==93
window.close();store.close()
'''
        with tempfile.TemporaryDirectory(prefix='compet-all-qt-') as directory:
            env=os.environ.copy();env.update(COMPET_TEST_PROFILE=directory,PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'),QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'))
            result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
