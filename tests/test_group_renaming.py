"""Qt creation and in-place group rename without losing tracking or associations."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GroupRenamingTests(unittest.TestCase):
    def test_create_rename_validate_capture_and_reload(self):
        probe = textwrap.dedent("""
            import copy, os, sys
            from pathlib import Path
            from unittest.mock import patch
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QApplication, QLineEdit
            from PyQt6.QtTest import QTest, QSignalSpy
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
            from core.timer_policy import matching_timer_ids
            from ui.components import ConfirmDialog, capture_bridge
            from ui.settings.main_window import MainSettingWindow
            I18n.set_language('zh_CN')
            config_mgr.config['groups'] = {'work':['Editor','App1','App2','App3','App4'],
                'other':['Game'],'分组 1':['Browser'],'分组 3':['Reader']}
            config_mgr.config['timers'] = [dict(id=str(i),name='Timer '+str(i),
                group=('work' if i < 2 else 'other'),idle_timeout=60,elapsed_seconds=i*100,
                is_fallback=i==3) for i in range(4)]
            before = copy.deepcopy(config_mgr.config)
            window = MainSettingWindow()
            window.show()
            tab = window.tab_timer
            tab.sub_tabs.setCurrentWidget(tab.sub_page_groups)
            app.processEvents()
            assert not hasattr(tab,'new_g_edit')
            assert not any(edit.placeholderText() == I18n.tr('new_group_placeholder')
                           for edit in tab.sub_page_groups.findChildren(QLineEdit))
            card = tab.group_list_layout.itemAt(0).widget()
            assert card.group_name == 'work' and len(card.slot_edits) == 5
            changes = QSignalSpy(tab.settings_changed)
            # Enter commits once, normalizes surrounding spaces, and preserves key ordering.
            QTest.mouseClick(card.name_edit,Qt.MouseButton.LeftButton)
            card.name_edit.selectAll()
            QTest.keyClicks(card.name_edit,'  Renamed  ')
            assert 'work' in config_mgr.config['groups'], 'Do not rename on every keystroke'
            QTest.keyClick(card.name_edit,Qt.Key.Key_Return)
            app.processEvents()
            assert len(changes) == 1
            assert card.name_edit.hasFocus()
            assert card.name_edit.text() == 'Renamed' and card.group_name == 'Renamed'
            assert tab.group_list_layout.itemAt(0).widget() is card
            saved = config_mgr.load_config()
            assert list(saved['groups']) == ['Renamed','other','分组 1','分组 3']
            assert saved['groups']['Renamed'] == before['groups']['work']
            assert [timer['group'] for timer in saved['timers']] == ['Renamed','Renamed','other','other']
            for old,new in zip(before['timers'],saved['timers']):
                assert {k:v for k,v in old.items() if k!='group'} == {k:v for k,v in new.items() if k!='group'}
            assert before['pets'] == saved['pets']
            assert matching_timer_ids(saved['timers'],saved['groups'],['Editor']) == ['0','1']
            assert tab.card_map['0'].group_combo.currentText() == 'Renamed'
            assert tab.card_map['1'].group_combo.currentText() == 'Renamed'
            assert tab.card_map['2'].group_combo.currentText() == 'other'
            # Empty and duplicate names never overwrite groups or update references.
            for bad,key in (('   ','group_name_empty'),('other','group_exists_warn')):
                baseline = copy.deepcopy(config_mgr.config)
                with patch.object(config_mgr,'save_config') as save:
                    card.name_edit.setText(bad)
                    QTest.keyClick(card.name_edit,Qt.Key.Key_Return)
                    assert not save.called
                assert config_mgr.config == baseline
                assert card.group_name == 'Renamed' and card.name_edit.text() == 'Renamed'
                assert card.name_error_label.text() == I18n.tr(key)
                assert card.name_error_label.isVisible()
            # Focus-out commits too; subsequent slot changes use the new key.
            card.name_edit.setText('Final')
            QTest.mouseClick(card.slot_edits[0],Qt.MouseButton.LeftButton)
            app.processEvents()
            assert card.group_name == 'Final' and not card.name_error_label.isVisible()
            card.slot_edits[4].setText('Updated4')
            assert config_mgr.load_config()['groups']['Final'][4] == 'Updated4'
            assert 'Renamed' not in config_mgr.config['groups']
            # Creating groups preserves existing cards, capture targets, and gives a selected name.
            with patch('ui.settings.tab_timer.start_window_click_capture'):
                QTest.mouseClick(card.slot_pick_btns[4],Qt.MouseButton.LeftButton)
                assert card.current_capturing_btn is card.slot_pick_btns[4]
                QTest.mouseClick(tab.btn_create_g,Qt.MouseButton.LeftButton)
                for _ in range(3): app.processEvents()
                assert list(config_mgr.config['groups'])[-1] == '分组 2'
                assert tab.group_list_layout.itemAt(0).widget() is card
                created = tab.group_list_layout.itemAt(4).widget()
                assert created.name_edit.hasFocus() and created.name_edit.selectedText() == '分组 2'
                assert card.current_capturing_btn is card.slot_pick_btns[4]
                tab.rename_group('Final','Captured group')
                capture_bridge.window_captured.emit('Captured4')
                assert config_mgr.load_config()['groups']['Captured group'][4] == 'Captured4'
                assert 'Final' not in config_mgr.config['groups']
                assert card.current_capturing_btn is None
            QTest.mouseClick(tab.btn_create_g,Qt.MouseButton.LeftButton)
            for _ in range(3): app.processEvents()
            assert list(config_mgr.config['groups'])[-1] == '分组 4'
            assert len(config_mgr.config['groups']) == 6
            for lang in ('zh_CN','en','ja','ko','zh_TW'):
                I18n.set_language(lang)
                assert card.name_edit.accessibleName() == I18n.tr('group_name')
                assert card.name_edit.toolTip() == I18n.tr('rename_group_hint')
            # Delete uses the current name after renaming and retains unrelated records.
            with patch.object(ConfirmDialog,'exec',return_value=ConfirmDialog.DialogCode.Accepted):
                QTest.mouseClick(card.del_btn,Qt.MouseButton.LeftButton)
            assert 'Captured group' not in config_mgr.load_config()['groups']
            assert card.isHidden()
            assert tab.card_map['0'].timer_data['group'] == 'other'
            assert [timer['elapsed_seconds'] for timer in config_mgr.config['timers']] == [0,100,200,300]

            preview = os.environ.get('COMPET_LAYOUT_PREVIEW_DIR')
            if preview:
                config_mgr.config['groups'] = {'工作':['Visual Studio Code','浏览器 - 文档','Terminal'],
                    '休息':['游戏','视频']}
                tab.refresh_group_list()
                I18n.set_language('zh_CN')
                for _ in range(4): app.processEvents()
                assert window.grab().save(str(Path(preview)/'group-renaming-preview.png'))
            reopened = MainSettingWindow()
            assert not hasattr(reopened.tab_timer,'new_g_edit')
            assert reopened.tab_timer.group_list_layout.count() == len(config_mgr.config['groups'])
            reopened.close()
            window.close()
        """)
        with tempfile.TemporaryDirectory(prefix='compet-group-rename-') as profile:
            env = os.environ.copy()
            env.update(COMPET_TEST_PROFILE=profile,USERPROFILE=profile,QT_QPA_PLATFORM='offscreen',
                       PYTHONUTF8='1',PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'))
            result = subprocess.run([sys.executable,'-X','utf8','-c',probe],cwd=ROOT,env=env,
                capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
