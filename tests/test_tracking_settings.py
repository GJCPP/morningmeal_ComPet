"""Qt integration: expandable tracking groups, fallback controls and pet input."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TrackingSettingsTests(unittest.TestCase):
    def test_expand_capture_save_fallback_and_global_pet_response(self):
        probe = textwrap.dedent("""
            import os
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
            from core.i18n import I18n
            I18n.set_language('zh_CN')
            config_mgr.config['groups'] = {'work': ['App0', 'App1', 'App2', 'App3', 'App4']}
            config_mgr.config['timers'][0]['group'] = 'work'
            from ui.settings.main_window import MainSettingWindow
            from ui.settings.tab_timer import GroupCardWidget
            from ui.components import capture_bridge, ConfirmDialog
            from ui.pet_widget import PetWidget
            from core.activity_engine import activity_engine
            from core.timer_policy import has_fallback_timer
            window = MainSettingWindow()
            window.show()
            window.tab_timer.sub_tabs.setCurrentIndex(1)
            app.processEvents()
            group = window.tab_timer.findChild(GroupCardWidget)
            assert len(group.slot_edits) == 5, 'Existing windows were truncated'
            group.slot_edits[0].setText('Updated0')
            assert config_mgr.config['groups']['work'][4] == 'App4'
            QTest.mouseClick(group.add_window_btn, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert len(group.slot_edits) == 6
            QTest.keyClicks(group.slot_edits[5], 'App5')
            with patch('ui.settings.tab_timer.start_window_click_capture') as start:
                QTest.mouseClick(group.slot_pick_btns[5], Qt.MouseButton.LeftButton)
                assert start.call_count == 1
                capture_bridge.window_captured.emit('Captured5')
            assert config_mgr.load_config()['groups']['work'] == ['Updated0', 'App1', 'App2', 'App3', 'App4', 'Captured5']
            window.tab_timer.refresh_group_list()
            assert len(window.tab_timer.group_list_layout.itemAt(0).widget().slot_edits) == 6

            window.tab_timer.sub_tabs.setCurrentIndex(0)
            app.processEvents()
            QTest.mouseClick(window.tab_timer.btn_add_fallback, Qt.MouseButton.LeftButton)
            app.processEvents()
            fallback = next(t for t in config_mgr.config['timers'] if t.get('is_fallback'))
            assert fallback['name'] == '其他'
            assert not window.tab_timer.btn_add_fallback.isEnabled()
            window.tab_timer.add_fallback_timer()
            assert sum(bool(t.get('is_fallback')) for t in config_mgr.config['timers']) == 1
            card = window.tab_timer.card_map[fallback['id']]
            assert not card.group_combo.isEnabled()
            card.name_edit.setText('Uncategorized')
            card.on_name_editing_finished()
            assert config_mgr.load_config()['timers'][-1]['is_fallback']
            I18n.set_language('en')
            assert card.group_combo.currentText() == 'Unmatched tasks'
            assert 'globally' in card.fallback_hint.text()

            pet_data = dict(config_mgr.config['pets'][0])
            pet_data['bound_timer_id'] = config_mgr.config['timers'][0]['id']
            pet = PetWidget(pet_data, lambda: [], lambda: None, None, None)
            with patch.object(activity_engine, 'is_timer_active', return_value=False):
                fallback['paused'] = True
                pet.trigger_bounce('a')
                pet.trigger_bounce('mouse_left')
                assert len(pet.hit_times) == 2, 'Fallback existence must allow global keyboard and mouse response'
                with patch.object(ConfirmDialog, 'exec', return_value=ConfirmDialog.DialogCode.Accepted):
                    window.tab_timer.remove_timer(fallback)
                assert not has_fallback_timer(config_mgr.config)
                assert window.tab_timer.btn_add_fallback.isEnabled()
                pet.trigger_bounce('a')
                assert len(pet.hit_times) == 2, 'Removing fallback must restore bound-timer gating'
            # Real controller + native timer widgets: all count, only first shows.
            from core.timer_policy import TimerSession
            from core.window_tracker import WindowInfo
            from ui.timer_widget import TimerWidget
            window.tab_timer.add_timer()
            timer_data = config_mgr.config['timers']
            made = []
            for timer in timer_data:
                made.append(TimerWidget(timer, lambda: made, lambda timer_id: None, lambda: None))
            controller.session = TimerSession(timer_data[-1]['id'])
            controller.foreground = lambda: WindowInfo(app_name='Updated0', window_id=123, pid=os.getpid()+100)
            controller.idle = lambda: 0
            controller.allowed = lambda: True
            controller.clock = lambda: 0
            before = [t.get('elapsed_seconds', 0) for t in timer_data]
            controller.step()
            controller.clock = lambda: 1
            controller.step()
            assert [t['elapsed_seconds'] for t in timer_data] == [value+1 for value in before]
            assert all(controller.is_active(t['id']) for t in timer_data)
            assert [widget.isVisible() for widget in made] == [True, False]
            assert controller.session.display_id == timer_data[0]['id']
            for widget in made:
                widget.close()
            pet.close()
            window.close()
        """)
        with tempfile.TemporaryDirectory(prefix='compet-tracking-ui-') as profile:
            env = os.environ.copy()
            env.update(USERPROFILE=profile, COMPET_TEST_PROFILE=profile,
                       QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1')
            env['PYTHONPATH'] = str(ROOT / 'morningmeal_Compet_V3')
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', probe], cwd=ROOT,
                env=env, capture_output=True, text=True, encoding='utf-8', timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
