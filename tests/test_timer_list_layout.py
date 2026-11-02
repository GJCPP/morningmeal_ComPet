"""Real Qt accordion, editing, ordering and overflow checks with isolated profiles."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TimerListLayoutTests(unittest.TestCase):
    def test_compact_list_stays_within_viewport_and_preserves_editors(self):
        probe = textwrap.dedent("""
            import os, sys
            from pathlib import Path
            from unittest.mock import patch
            from PyQt6.QtCore import Qt, QPoint
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtTest import QTest
            app = QApplication([])
            if sys.platform == 'win32':
                from PyQt6.QtGui import QFontDatabase
                for name in ('segoeui.ttf','segoeuib.ttf','seguisym.ttf','msyh.ttc','msyhbd.ttc','malgun.ttf'):
                    QFontDatabase.addApplicationFont(str(Path(os.environ['SystemRoot']) / 'Fonts' / name))
            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
            from core.interaction_fixes import install
            install()
            from core.timer_fixes import install as install_timer
            install_timer()
            from core.i18n import I18n
            from ui.settings.main_window import MainSettingWindow
            long_group = 'LongGroupWithoutSpaces' * 12
            config_mgr.config['groups'] = {long_group: ['Editor']}
            config_mgr.config['timers'] = [
                dict(id=str(i), name=('LongTimerWithoutSpaces' * 20 if i == 0 else 'Timer ' + str(i)),
                     group=long_group, idle_timeout=60, elapsed_seconds=36000000 if i == 0 else i * 60,
                     is_fallback=i == 23) for i in range(24)]
            window = MainSettingWindow()
            window.show()
            app.processEvents()
            tab = window.tab_timer
            scroll = tab.timer_scroll
            first = tab.card_map['0']
            second = tab.card_map['1']
            last = tab.card_map['23']
            assert first.expand_btn.isChecked() and first.details.isVisible()
            assert not second.details.isVisible()

            def no_horizontal_overflow(card):
                for _ in range(3): app.processEvents()
                assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                assert not scroll.horizontalScrollBar().isVisible()
                assert scroll.widget().width() <= scroll.viewport().width(), (scroll.widget().width(), scroll.viewport().width())
                assert scroll.horizontalScrollBar().maximum() == 0
                for row in tab.card_map.values():
                    assert row.width() <= scroll.viewport().width()
                    assert row.x() + row.width() <= scroll.widget().width()
                    assert row.expand_btn.width() >= 40
                widgets = [card.expand_btn, card.time_label, card.move_up_btn, card.move_down_btn]
                if card.expand_btn.isChecked():
                    widgets += [card.name_edit, card.group_combo, card.idle_spin, card.btn_reset, card.del_btn]
                for widget in widgets:
                    x = widget.mapTo(card, QPoint(0,0)).x()
                    assert x >= 0 and x + widget.width() <= card.width(), (widget.objectName(), x, widget.width(), card.width())

            for lang in ('zh_CN','en','ja','ko','zh_TW'):
                I18n.set_language(lang)
                for dark in (False,True):
                    config_mgr.config['settings']['dark_mode'] = dark
                    window.is_dark = dark
                    window.apply_theme()
                    first.set_expanded(True)
                    no_horizontal_overflow(first)
                    last.set_expanded(True)
                    no_horizontal_overflow(last)
                    assert last.details.isVisible() and not first.details.isVisible()
                    assert not last.group_combo.isEnabled()
                    assert last.fallback_hint.isVisible()
            assert scroll.verticalScrollBar().maximum() > 0
            # Real input expands one row, persists edits, and keeps it alive on refresh/reorder.
            scroll.ensureWidgetVisible(second.expand_btn)
            app.processEvents()
            QTest.mouseClick(second.expand_btn, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert second.details.isVisible() and not last.details.isVisible()
            QTest.mouseClick(second.name_edit, Qt.MouseButton.LeftButton)
            second.name_edit.selectAll()
            QTest.keyClicks(second.name_edit, 'Edited')
            tab.refresh_timer_list()
            app.processEvents()
            assert tab.card_map['1'] is second and second.name_edit.hasFocus()
            QTest.keyClick(second.name_edit, Qt.Key.Key_Tab)
            assert config_mgr.load_config()['timers'][1]['name'] == 'Edited'
            tab.move_timer('1', -1)
            app.processEvents()
            assert tab.card_map['1'] is second and second.details.isVisible()
            assert tab.timer_list_layout.itemAt(0).widget() is second
            assert config_mgr.load_config()['timers'][0]['id'] == '1'
            tab.on_activity_tick({'0': 123})
            assert first.time_label.text() == '00:02:03' and not first.details.isVisible()
            QTest.mouseClick(second.expand_btn, Qt.MouseButton.LeftButton)
            tab.refresh_timer_list()
            assert not any(card.expand_btn.isChecked() for card in tab.card_map.values())
            tab.add_timer()
            app.processEvents()
            added_id = config_mgr.config['timers'][-1]['id']
            added = tab.card_map[added_id]
            assert added.details.isVisible()
            assert tab.card_map['1'] is second
            no_horizontal_overflow(added)

            # Render the real settings widget, using sample records only.
            preview = os.environ.get('COMPET_LAYOUT_PREVIEW_DIR')
            if preview and os.environ['QT_SCALE_FACTOR'] == '1':
                config_mgr.config['timers'] = [dict(id=str(i), name=name, group=long_group, idle_timeout=60,
                    elapsed_seconds=seconds,is_fallback=i==3) for i,(name,seconds) in enumerate(
                    [('工作',4144),('摸鱼',3490),('浏览',900),('其他',0)])]
                config_mgr.config['groups'] = {'工作': ['Editor'], '摸鱼': ['Game'], '浏览器': ['Browser']}
                for timer, group in zip(config_mgr.config['timers'], ('工作','摸鱼','浏览器','')):
                    timer['group'] = group
                tab._expanded_timer_id = '0'
                tab.refresh_timer_list()
                I18n.set_language('zh_CN')
                config_mgr.config['settings']['dark_mode'] = False
                window.is_dark = False
                window.apply_theme()
                window.resize(window.width(),720)
                for _ in range(4): app.processEvents()
                assert len(tab.card_map) == 4
                assert tab.timer_list_layout.count() == 4
                assert window.grab().save(str(Path(preview) / 'timer-list-preview.png'))
            window.close()
        """)
        for scale in ('1','1.5','2'):
            with self.subTest(scale=scale), tempfile.TemporaryDirectory(prefix='compet-timer-list-') as profile:
                env = os.environ.copy()
                env.update(COMPET_TEST_PROFILE=profile,USERPROFILE=profile,QT_QPA_PLATFORM='offscreen',
                           QT_SCALE_FACTOR=scale,PYTHONUTF8='1',PYTHONPATH=str(ROOT / 'morningmeal_Compet_V3'))
                result = subprocess.run([sys.executable,'-X','utf8','-c',probe],env=env,cwd=ROOT,
                    capture_output=True,text=True,encoding='utf-8',timeout=35)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
