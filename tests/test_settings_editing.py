"""Exercise timer settings through real Qt mouse and keyboard events."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TimerSettingsEditingTests(unittest.TestCase):
    def test_rename_then_click_idle_keeps_focus_and_saves(self):
        probe = textwrap.dedent("""
            import json
            import os
            from pathlib import Path
            from unittest.mock import patch
            from PyQt6.QtCore import Qt
            from PyQt6.QtTest import QTest, QSignalSpy
            from PyQt6.QtWidgets import QApplication

            app = QApplication([])
            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr, CONFIG_PATH
            from core.interaction_fixes import install
            install()
            from core.timer_fixes import install as install_timer
            install_timer()
            from core.config_manager import config_mgr, CONFIG_PATH
            from ui.settings.main_window import MainSettingWindow

            window = MainSettingWindow()
            window.show()
            app.processEvents()
            updates = QSignalSpy(window.settings_updated)
            timer = config_mgr.config['timers'][0]
            card = window.tab_timer.card_map[timer['id']]
            QTest.mouseClick(card.name_edit, Qt.MouseButton.LeftButton)
            QTest.keyClick(card.name_edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(card.name_edit, 'Focus test')
            QTest.mouseClick(card.idle_spin, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert window.tab_timer.card_map[timer['id']] is card, 'Name save recreated the focused timer card'
            assert card.idle_spin.hasFocus(), 'Click did not focus the idle editor'
            QTest.keyClick(card.idle_spin, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(card.idle_spin, '60')
            QTest.keyClick(card.idle_spin, Qt.Key.Key_Tab)
            app.processEvents()
            assert timer['idle_timeout'] == 60, timer
            assert len(updates) >= 1, 'Name changes must still synchronize desktop widgets'
            saved = json.loads(Path(CONFIG_PATH).read_text(encoding='utf-8'))
            assert saved['timers'][0]['name'] == 'Focus test', saved
            assert saved['timers'][0]['idle_timeout'] == 60, saved

            # Tab navigation after another rename must reach the same editor.
            QTest.mouseClick(card.name_edit, Qt.MouseButton.LeftButton)
            QTest.keyClicks(card.name_edit, ' again')
            for _ in range(4):
                QTest.keyClick(app.focusWidget(), Qt.Key.Key_Tab)
                app.processEvents()
                if card.idle_spin.hasFocus():
                    break
            assert card.idle_spin.hasFocus(), 'Tab navigation lost the idle editor'
            QTest.keyClick(card.idle_spin, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(card.idle_spin, '120')
            QTest.keyClick(card.idle_spin, Qt.Key.Key_Tab)
            app.processEvents()
            assert timer['idle_timeout'] == 120, timer
            window.close()
            reopened = MainSettingWindow()
            reopened.show()
            app.processEvents()
            assert reopened.tab_timer.card_map[timer['id']].idle_spin.value() == 120
            assert config_mgr.load_config()['timers'][0]['idle_timeout'] == 120
            reopened.close()
        """)
        with tempfile.TemporaryDirectory(prefix='compet-settings-edit-') as profile:
            env = os.environ.copy()
            env.update(USERPROFILE=profile, COMPET_TEST_PROFILE=profile, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1')
            env['PYTHONPATH'] = str(ROOT / 'morningmeal_Compet_V3')
            result = subprocess.run(
                [sys.executable, '-X', 'utf8', '-c', probe],
                cwd=ROOT, env=env, capture_output=True, text=True,
                encoding='utf-8', timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


    def test_idle_text_has_visible_space_at_display_scales(self):
        probe = textwrap.dedent("""
            import os
            from unittest.mock import patch
            from PyQt6.QtWidgets import QApplication, QStyle, QStyleOptionFrame
            app = QApplication([])
            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
            from core.i18n import I18n
            I18n.set_language('en')
            from core.interaction_fixes import install
            install()
            from core.timer_fixes import install as install_timer
            install_timer()
            from ui.settings.main_window import MainSettingWindow
            window = MainSettingWindow()
            window.show()
            app.processEvents()
            for dark in (False, True):
                window.is_dark = dark
                config_mgr.config['settings']['dark_mode'] = dark
                window.apply_theme()
                app.processEvents()
                spin = next(iter(window.tab_timer.card_map.values())).idle_spin
                editor = spin.lineEdit()
                option = QStyleOptionFrame()
                option.initFrom(editor)
                option.rect = editor.rect()
                contents = editor.style().subElementRect(QStyle.SubElement.SE_LineEditContents, option, editor)
                required_width = editor.fontMetrics().horizontalAdvance(spin.text()) + 6
                assert contents.width() >= required_width, (dark, contents.getRect(), required_width)
                assert contents.height() >= editor.fontMetrics().height(), (dark, contents.getRect())
                # Verify real painted glyphs, not just an internally stored value.
                editor.clearFocus()
                app.processEvents()
                painted = editor.grab().toImage()
                original = editor.text()
                editor.setText('')
                app.processEvents()
                blank = editor.grab().toImage()
                differences = sum(painted.pixel(x, y) != blank.pixel(x, y)
                    for y in range(min(painted.height(), blank.height()))
                    for x in range(min(painted.width(), blank.width())))
                assert differences >= 12, ('No visible numeric text', dark, differences)
                editor.setText(original)
            window.close()
        """)
        for scale in ('1', '1.5', '2'):
            with self.subTest(scale=scale), tempfile.TemporaryDirectory(prefix='compet-idle-paint-') as profile:
                env = os.environ.copy()
                env.update(USERPROFILE=profile, COMPET_TEST_PROFILE=profile,
                           QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=scale, PYTHONUTF8='1')
                env['PYTHONPATH'] = str(ROOT / 'morningmeal_Compet_V3')
                result = subprocess.run([sys.executable, '-X', 'utf8', '-c', probe],
                    cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()