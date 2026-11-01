"""Real Qt sorting, cancel/confirm reset and fractional accounting regression."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
ROOT = Path(__file__).resolve().parents[1]


class TimerOrderResetTests(unittest.TestCase):
    def test_reorder_priority_persistence_and_confirmed_reset(self):
        probe = textwrap.dedent("""
            import copy, os
            from unittest.mock import patch
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt
            from PyQt6.QtTest import QTest
            app = QApplication([])
            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
            from core.interaction_fixes import install
            install()
            from core.timer_fixes import install as install_timer, controller
            install_timer()
            from core.timer_policy import TimerSession
            from core.window_tracker import WindowInfo
            from core.activity_engine import activity_engine
            from ui.components import ConfirmDialog
            from ui.settings.main_window import MainSettingWindow
            from ui.timer_statistics import TimerStatisticsDialog
            from core.i18n import I18n
            I18n.set_language('zh_CN')
            config_mgr.config['groups'] = {'shared': ['Editor']}
            config_mgr.config['timers'] = [
                dict(id='a',name='First',group='shared',idle_timeout=60,elapsed_seconds=10),
                dict(id='b',name='Second',group='shared',idle_timeout=60,elapsed_seconds=20),
                dict(id='other',name='Other',group='',is_fallback=True,idle_timeout=60,elapsed_seconds=5)]
            window = MainSettingWindow()
            window.show()
            app.processEvents()
            tab = window.tab_timer
            assert not tab.card_map['a'].move_up_btn.isEnabled()
            assert not tab.card_map['other'].move_down_btn.isEnabled()
            with patch.object(config_mgr, 'save_config') as save:
                tab.move_timer('a', -1)
                tab.move_timer('missing', 1)
                tab.move_timer('a', 9)
                assert save.call_count == 0
            QTest.mouseClick(tab.card_map['b'].move_up_btn, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert [t['id'] for t in config_mgr.load_config()['timers']] == ['b', 'a', 'other']
            assert [t['elapsed_seconds'] for t in config_mgr.config['timers']] == [20, 10, 5]
            assert tab.card_map['b'].position_label.text() == '顺序 1'
            controller.session = TimerSession('a')
            controller.foreground = lambda: WindowInfo(app_name='Editor',window_id=123,pid=os.getpid()+100)
            controller.idle = lambda: 0
            controller.allowed = lambda: True
            controller.clock = lambda: 0
            controller.step()
            assert controller.session.display_id == 'b'
            controller.clock = lambda: 1
            controller.step()
            before = copy.deepcopy(config_mgr.config)
            controller.session.fractions = {'a': 0.9, 'b': 0.9, 'other': 0.2}
            with patch.object(ConfirmDialog, 'exec', return_value=ConfirmDialog.DialogCode.Rejected):
                with patch.object(config_mgr, 'save_config') as save:
                    QTest.mouseClick(tab.btn_reset_all, Qt.MouseButton.LeftButton)
                    assert save.call_count == 0
            assert config_mgr.config == before, 'Cancelling reset changed configuration'
            assert controller.session.fractions['a'] == 0.9
            with patch.object(ConfirmDialog, 'exec', return_value=ConfirmDialog.DialogCode.Accepted):
                QTest.mouseClick(tab.btn_reset_all, Qt.MouseButton.LeftButton)
            assert all(t['elapsed_seconds'] == 0 for t in config_mgr.load_config()['timers'])
            assert controller.session.fractions == {}
            assert controller.session.counting_ids == set()
            for old, new in zip(before['timers'], config_mgr.config['timers']):
                assert {k:v for k,v in old.items() if k != 'elapsed_seconds'} == {k:v for k,v in new.items() if k != 'elapsed_seconds'}
                assert tab.card_map[new['id']].time_label.text() == '00:00:00'
            assert before['groups'] == config_mgr.config['groups']
            assert before['pets'] == config_mgr.config['pets']
            controller.clock = lambda: 1.1
            controller.step()
            controller.clock = lambda: 1.4
            controller.step()
            assert all(t['elapsed_seconds'] == 0 for t in config_mgr.config['timers'])
            stats = TimerStatisticsDialog()
            assert stats.chart.total == 0
            controller.clock = lambda: 2.2
            controller.step()
            assert [t['elapsed_seconds'] for t in config_mgr.config['timers']] == [1, 1, 0]
            controller.session.fractions = {'a': 0.8, 'b': 0.7}
            activity_engine.reset_timers(['a'])
            assert controller.session.fractions == {'b': 0.7}
            assert [t['elapsed_seconds'] for t in config_mgr.config['timers']] == [1, 0, 0]
            config_mgr.config['timers'].clear()
            tab.refresh_timer_list()
            assert not tab.btn_reset_all.isEnabled()
            stats.close()
            window.close()
        """)
        with tempfile.TemporaryDirectory(prefix='compet-order-reset-') as profile:
            env = os.environ.copy()
            env.update(USERPROFILE=profile,COMPET_TEST_PROFILE=profile,
                       QT_QPA_PLATFORM='offscreen',PYTHONUTF8='1')
            env['PYTHONPATH'] = str(ROOT / 'morningmeal_Compet_V3')
            result = subprocess.run([sys.executable,'-X','utf8','-c',probe],cwd=ROOT,
                env=env,capture_output=True,text=True,encoding='utf-8',timeout=25)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
