"""Read-only pie chart totals and real Qt entry-point regression."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'morningmeal_Compet_V3'))
from core.timer_statistics import timer_distribution


class TimerDistributionTests(unittest.TestCase):
    def test_all_timers_including_zero_and_fallback_are_retained(self):
        timers = [{'id': 'a', 'name': 'Work', 'elapsed_seconds': 60},
                  {'id': 'b', 'name': 'Study', 'elapsed_seconds': 30, 'paused': True},
                  {'id': 'c', 'name': 'Other', 'elapsed_seconds': 10, 'is_fallback': True},
                  {'id': 'd', 'name': 'New', 'elapsed_seconds': 0}]
        before = copy.deepcopy(timers)
        rows, total = timer_distribution(timers)
        self.assertEqual(total, 100)
        self.assertEqual([r['share'] for r in rows], [0.6, 0.3, 0.1, 0])
        self.assertEqual(timers, before)

    def test_empty_and_zero_totals_do_not_divide_by_zero(self):
        self.assertEqual(timer_distribution([]), ([], 0))
        rows, total = timer_distribution([{'id': 'a', 'elapsed_seconds': 0}])
        self.assertEqual(total, 0)
        self.assertEqual(rows[0]['share'], 0)

    def test_malformed_times_are_zero(self):
        for value in [None, 'bad', -20, float('nan'), float('inf')]:
            with self.subTest(value=value):
                rows, total = timer_distribution([{'elapsed_seconds': value}])
                self.assertEqual(total, 0)
                self.assertEqual(rows[0]['seconds'], 0)

    def test_overlapping_totals_are_not_deduplicated(self):
        rows, total = timer_distribution([{'elapsed_seconds': 3600}, {'elapsed_seconds': 3600}])
        self.assertEqual(total, 7200)
        self.assertEqual([row['share'] for row in rows], [0.5, 0.5])


class TimerStatisticsQtTests(unittest.TestCase):
    def test_open_render_live_update_empty_and_reopen_without_saving(self):
        probe = textwrap.dedent("""
            import copy, os
            from unittest.mock import patch
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QColor
            from PyQt6.QtTest import QTest
            app = QApplication([])
            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
            from core.interaction_fixes import install
            install()
            from core.timer_fixes import install as install_timer
            install_timer()
            from core.i18n import I18n
            I18n.set_language('en')
            config_mgr.config['timers'] = [
                dict(id='work', name='Work', elapsed_seconds=3600, group=''),
                dict(id='study', name='Study', elapsed_seconds=1800, group='', paused=True),
                dict(id='other', name='Other', elapsed_seconds=600, group='', is_fallback=True),
                dict(id='new', name='New', elapsed_seconds=0, group='')]
            from ui.settings.main_window import MainSettingWindow
            from ui.mini_dialogs import TimerMiniDialog
            import ui.timer_statistics as module
            window = MainSettingWindow()
            window.show()
            app.processEvents()
            original = copy.deepcopy(config_mgr.config)
            with patch.object(config_mgr, 'save_config', side_effect=AssertionError('Statistics must not save config')):
                QTest.mouseClick(window.tab_timer.btn_statistics, Qt.MouseButton.LeftButton)
                app.processEvents()
                dialog = module._dialog
                assert dialog.isVisible()
                assert dialog.table.rowCount() == 4
                assert dialog.table.item(0, 2).text() == '60.0%'
                assert dialog.table.item(3, 2).text() == '0.0%'
                assert dialog.chart.total == 6000
                image = dialog.chart.grab().toImage()
                painted = {image.pixelColor(x, y).name()
                    for y in range(image.height()) for x in range(image.width())}
                assert all(color.lower() in painted for color in module.COLORS[:3]), 'Missing pie slices'
                assert config_mgr.config == original
                config_mgr.config['timers'][0]['elapsed_seconds'] = 4600
                QTest.qWait(1150)
                assert dialog.chart.total == 7000, 'Open chart did not refresh'
                config_mgr.config['settings']['dark_mode'] = True
                I18n.set_language('zh_CN')
                dialog.refresh()
                assert dialog.windowTitle() == '时间分布'
                assert dialog.table.horizontalHeaderItem(2).text() == '占比'
                assert dialog.chart.grab().width() > 0
                for timer in config_mgr.config['timers']:
                    timer['elapsed_seconds'] = 0
                dialog.refresh()
                assert dialog.chart.total == 0
                assert dialog.chart.grab().width() > 0
                config_mgr.config['timers'].clear()
                dialog.refresh()
                assert dialog.table.rowCount() == 0
                dialog.close()
                assert not dialog.refresh_timer.isActive()
                mini = TimerMiniDialog({'id': 'x'}, lambda: None)
                mini.show()
                QTest.mouseClick(mini.statistics_btn, Qt.MouseButton.LeftButton)
                app.processEvents()
                assert module._dialog is dialog and dialog.isVisible()
                assert dialog.refresh_timer.isActive()
                dialog.close()
                window.close()
        """)
        with tempfile.TemporaryDirectory(prefix='compet-statistics-test-') as profile:
            env = os.environ.copy()
            env.update(USERPROFILE=profile, COMPET_TEST_PROFILE=profile,
                       QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1')
            env['PYTHONPATH'] = str(ROOT / 'morningmeal_Compet_V3')
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', probe], cwd=ROOT,
                env=env, capture_output=True, text=True, encoding='utf-8', timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
