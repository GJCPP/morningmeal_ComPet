"""Check statistics controls against OS/app palette mismatches on real Qt."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class StatisticsControlTests(unittest.TestCase):
    def test_text_date_navigation_and_no_explanatory_footer(self):
        probe=r'''
import os
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette,QColor
from PyQt6.QtCore import Qt,QDate,QPoint
from PyQt6.QtTest import QTest
app=QApplication([])
# Deliberately make the OS/application dark while rendering both dialog themes.
palette=app.palette()
for role in (QPalette.ColorRole.Base,QPalette.ColorRole.Window,QPalette.ColorRole.Button):
    palette.setColor(role,QColor('#121212'))
for role in (QPalette.ColorRole.Text,QPalette.ColorRole.WindowText,QPalette.ColorRole.ButtonText):
    palette.setColor(role,QColor('#eeeeee'))
app.setPalette(palette)
with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
    from core.config_manager import config_mgr
from core.i18n import I18n
from ui.timer_statistics import TimerStatisticsDialog
from core.timer_history import get_history_store
window=TimerStatisticsDialog();window.show();app.processEvents()
for lang in ('zh_CN','en'):
    I18n.set_language(lang)
    for dark in (False,True):
        config_mgr.config['settings']['dark_mode']=dark
        for mode in range(5):
            window.period_combo.setCurrentIndex(mode);window.refresh();app.processEvents()
            assert window.period_combo.currentText()
            assert not window.note_label.isVisible()
            combo=window.period_combo
            before=combo.grab().toImage();text=combo.itemText(mode)
            combo.setItemText(mode,'');app.processEvents();blank=combo.grab().toImage()
            assert sum(before.pixel(x,y)!=blank.pixel(x,y) for y in range(before.height()) for x in range(before.width()))>=12,('invisible combo text',lang,dark,mode)
            combo.setItemText(mode,text)
            for button in (window.previous_button,window.next_button):
                before=button.grab().toImage();label=button.text();button.setText('');app.processEvents();blank=button.grab().toImage()
                assert sum(before.pixel(x,y)!=blank.pixel(x,y) for y in range(before.height()) for x in range(before.width()))>=4,('invisible navigation arrow',dark,mode)
                button.setText(label)
            editor=window.date_edit.lineEdit();editor.deselect();editor.clearFocus();app.processEvents()
            assert editor.text() and editor.width()>90
            before=editor.grab().toImage();text=editor.text();editor.setText('');app.processEvents();blank=editor.grab().toImage()
            assert sum(before.pixel(x,y)!=blank.pixel(x,y) for y in range(before.height()) for x in range(before.width()))>=12,('invisible date text',lang,dark,mode)
            editor.setText(text)
            expected='#A1A1AA' if dark else '#6B7280'
            if mode in (0,4):
                assert not window.date_edit.isEnabled()
                assert window.date_edit.palette().color(QPalette.ColorGroup.Disabled,QPalette.ColorRole.Text).name().lower()==expected.lower()
            else:
                assert window.date_edit.isEnabled()
window.period_combo.setCurrentIndex(1)
window.date_edit.setDate(QDate(2026,11,3));QTest.mouseClick(window.next_button,Qt.MouseButton.LeftButton)
assert window.date_edit.date()==QDate(2026,11,4)
QTest.mouseClick(window.previous_button,Qt.MouseButton.LeftButton)
assert window.date_edit.date()==QDate(2026,11,3)
window.period_combo.showPopup();app.processEvents();assert window.period_combo.view().isVisible();window.period_combo.hidePopup()
QTest.mouseClick(window.date_edit,Qt.MouseButton.LeftButton,pos=QPoint(window.date_edit.width()-8,window.date_edit.height()//2));app.processEvents();assert window.date_edit.calendarWidget().isVisible();QTest.keyClick(window.date_edit.calendarWidget(),Qt.Key.Key_Escape);app.processEvents();assert not window.date_edit.calendarWidget().isVisible()
# Actual errors remain visible; routine instructions never take chart space.
store=get_history_store();store.last_error='OperationalError';window.refresh()
assert window.note_label.isVisible() and window.note_label.text()
store.last_error=None;window.refresh();assert not window.note_label.isVisible()
window.clearFocus();app.processEvents();window.close();app.processEvents()
print('PASS: text painted in every mode/theme, disabled date contrast, popups, navigation and error-only footer')
'''
        with tempfile.TemporaryDirectory(prefix='compet-stats-style-') as profile:
            env=os.environ.copy();env.update(COMPET_TEST_PROFILE=profile,PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'),QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'))
            result=subprocess.run([sys.executable,'-c',probe],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
