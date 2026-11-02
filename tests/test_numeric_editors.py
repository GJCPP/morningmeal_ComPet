"""All settings number fields must paint, accept replacement typing and persist."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NumericEditorTests(unittest.TestCase):
    def test_all_number_fields_across_themes_scales_and_rebuild_notifications(self):
        probe = textwrap.dedent('''
            import os
            from unittest.mock import patch
            from PyQt6.QtWidgets import QApplication, QSpinBox, QStyle, QStyleOptionFrame
            from PyQt6.QtCore import Qt
            from PyQt6.QtTest import QTest
            app = QApplication([])
            with patch('os.path.expanduser', return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
            from core.interaction_fixes import install
            install()
            from core.timer_fixes import install as install_timer
            install_timer()
            from core.i18n import I18n
            from ui.settings.main_window import MainSettingWindow
            from ui.numeric_editor import SettingsSpinBox
            window = MainSettingWindow()
            window.show()
            app.processEvents()
            pet = config_mgr.config['pets'][0]
            timer = config_mgr.config['timers'][0]
            card = window.tab_pet.pet_grid.itemAt(0).widget()
            idle_card = window.tab_timer.card_map[timer['id']]
            assert len(window.findChildren(QSpinBox)) == 2
            assert all(isinstance(spin,SettingsSpinBox) for spin in window.findChildren(QSpinBox))
            for lang in ('zh_CN', 'en'):
                I18n.set_language(lang)
                for dark in (False,True):
                    config_mgr.config['settings']['dark_mode']=dark
                    window.is_dark=dark
                    window.apply_theme()
                    for kind in ('scale','idle'):
                        window.tabs.setCurrentWidget(window.tab_pet if kind=='scale' else window.tab_timer)
                        if kind=='scale': window.tab_pet.sub_tabs.setCurrentWidget(window.tab_pet.sub_page_pets)
                        spin = card.scale_spin if kind=='scale' else idle_card.idle_spin
                        app.processEvents()
                        QTest.mouseClick(spin.lineEdit(),Qt.MouseButton.LeftButton)
                        spin.selectAll()
                        QTest.keyClicks(spin.lineEdit(),'125' if kind=='scale' else '120')
                        app.processEvents()
                        assert spin.hasFocus() or spin.lineEdit().hasFocus()
                        # A live external refresh must preserve the active pet editor.
                        if kind=='scale':
                            window.tab_pet.refresh_pet_list()
                            assert window.tab_pet.pet_grid.itemAt(0).widget() is card
                            assert '125' in spin.lineEdit().text()
                        QTest.keyClick(spin.lineEdit(),Qt.Key.Key_Return)
                        app.processEvents()
                        saved=config_mgr.load_config()
                        assert saved['pets'][0]['scale']==1.25 if kind=='scale' else saved['timers'][0]['idle_timeout']==120
                        if kind=='scale': assert window.tab_pet.pet_grid.itemAt(0).widget() is card
                        editor=spin.lineEdit()
                        opt=QStyleOptionFrame(); opt.initFrom(editor); opt.rect=editor.rect()
                        rect=editor.style().subElementRect(QStyle.SubElement.SE_LineEditContents,opt,editor)
                        assert rect.width() >= editor.fontMetrics().horizontalAdvance(spin.text())+4,(kind,rect.getRect(),spin.text())
                        assert rect.height() >= editor.fontMetrics().height(),(kind,rect.getRect())
                        editor.clearFocus(); app.processEvents()
                        painted=editor.grab().toImage(); text=editor.text(); editor.setText(''); app.processEvents()
                        blank=editor.grab().toImage()
                        assert sum(painted.pixel(x,y)!=blank.pixel(x,y) for y in range(painted.height()) for x in range(painted.width())) >= 12
                        editor.setText(text)
            # Tab commits a range-valid replacement; steppers still work.
            window.tabs.setCurrentWidget(window.tab_pet)
            spin=card.scale_spin
            spin.setFocus(); spin.selectAll(); QTest.keyClicks(spin.lineEdit(),'10')
            QTest.keyClick(spin.lineEdit(),Qt.Key.Key_Tab);app.processEvents()
            assert config_mgr.load_config()['pets'][0]['scale']==0.10
            spin.stepUp();app.processEvents()
            assert config_mgr.load_config()['pets'][0]['scale']==0.15
            reopened=MainSettingWindow()
            assert reopened.tab_pet.pet_grid.itemAt(0).widget().scale_spin.value()==15
            assert next(iter(reopened.tab_timer.card_map.values())).idle_spin.value()==120
            window.close(); reopened.close()
        ''')
        for scale in ('1','1.5','2'):
            with self.subTest(scale=scale), tempfile.TemporaryDirectory(prefix='compet-number-test-') as profile:
                env=os.environ.copy()
                env.update(COMPET_TEST_PROFILE=profile,QT_QPA_PLATFORM=os.environ.get('COMPET_QT_TEST_PLATFORM','offscreen'),QT_SCALE_FACTOR=scale,
                           PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'))
                result=subprocess.run([sys.executable,'-c',probe],env=env,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
