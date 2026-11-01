"""Run in a repaired Qt runtime with permission APIs mocked to denied.

The harness must intercept configuration writes; no real input is posted.
"""

def run():
    import json
    from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel
    from PyQt6 import sip
    from core.config_manager import config_mgr
    from core.i18n import I18n
    from ui.timer_widget import TimerWidget
    from ui.pet_widget import PetWidget
    from ui.components import ConfirmDialog
    from ui.settings.main_window import MainSettingWindow

    old_config = config_mgr.config
    old_save = config_mgr.save_config
    old_save_skin = config_mgr.save_skin_config
    old_language = I18n.get_lang()
    created = []
    saves = []
    passed = []
    timers = []
    from core.interaction_fixes import _remove_unused_default_group
    import core.config_manager as config_module
    assert config_module.DEFAULT_CONFIG['groups'] == {}
    legacy = {'groups': {'기본 그룹':['','',''], '工作':['Logseq']}, 'timers':[{'group':'工作','elapsed_seconds':130}]}
    assert _remove_unused_default_group(legacy)
    assert legacy['groups'] == {'工作':['Logseq']} and legacy['timers'][0]['elapsed_seconds'] == 130
    assert not _remove_unused_default_group({'groups':{'기본 그룹':['Logseq']}, 'timers':[]})
    assert not _remove_unused_default_group({'groups':{'기본 그룹':['','','']}, 'timers':[{'group':'기본 그룹'}]})
    passed.append('no automatic group; only empty unused legacy group removed; active and populated groups preserved')
    try:
        config_mgr.config = json.loads(json.dumps(old_config))
        config_mgr.config['settings'].update(magnetic_snap=True, snap_distance=15, clamp_to_screen=False, dark_mode=False)
        config_mgr.config['groups'] = {'probe': []}
        config_mgr.save_config = lambda: saves.append(True)
        config_mgr.save_skin_config = lambda *args, **kwargs: None
        timer_data = dict(id='probe-timer', name='probe', group='probe', elapsed_seconds=0, paused=False, x=900, y=900)
        pet_data = dict(id='probe-pet', skin='default', bound_timer_id='', x=100, y=100, scale=1)
        config_mgr.config['timers'] = [timer_data]
        config_mgr.config['pets'] = [pet_data]

        class ProbePet(PetWidget):
            def __init__(self):
                QWidget.__init__(self)
                self.pet_data = pet_data
                self.get_all_timers_callback = lambda: timers
                self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
                self.resize(544, 432)
                self.move(100, 100)
                self.show()
            def paintEvent(self, event):
                pass
        pet = ProbePet()
        created.append(pet)
        bound = lambda timer_id: pet if pet.pet_data.get('bound_timer_id') == timer_id else None
        timer = TimerWidget(timer_data, lambda: timers, bound, lambda: None)
        created.append(timer)
        timers.append(timer)
        timer.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        timer.show()

        def event(kind, target, global_pos, button, buttons):
            local = target.mapFromGlobal(global_pos)
            return QMouseEvent(kind, QPointF(local), QPointF(global_pos), button, buttons, Qt.KeyboardModifier.NoModifier)
        def drag(target, destination):
            start = target.mapToGlobal(QPoint(5, 5))
            delta = destination - timer.pos()
            QApplication.sendEvent(target, event(QEvent.Type.MouseButtonPress,target,start,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton))
            QApplication.sendEvent(target, event(QEvent.Type.MouseMove,target,start+delta,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton))
            QApplication.sendEvent(target, event(QEvent.Type.MouseButtonRelease,target,start+delta,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton))

        drag(timer.label_name, QPoint(1080, 980))
        assert timer.pos() == QPoint(1080, 980), timer.pos()
        drag(timer.label_time, QPoint(950, 830))
        assert timer.pos() == QPoint(950, 830), timer.pos()
        passed.append('drag from both name and time labels')

        target = QPoint(302, 528)
        drag(timer.label_name, target)
        assert timer.pos() == target
        assert pet.pet_data['bound_timer_id'] == timer_data['id']
        assert pet.pos() == QPoint(100, 100)
        passed.append('timer docks below a 544x432 pet without moving the pet')
        drag(timer.label_time, QPoint(382, 568))
        assert pet.pos() == QPoint(180, 140), pet.pos()
        assert timer_data['x'] == 382 and pet_data['x'] == 180
        passed.append('bound pair drags together and saves both positions')

        pet.unbind_timer()
        timer.move(500, 600)
        pet.move(298, 172)
        release = event(QEvent.Type.MouseButtonRelease, pet, pet.mapToGlobal(QPoint(200, 300)), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
        pet.mouseReleaseEvent(release)
        assert pet.pet_data['bound_timer_id'] == timer_data['id']
        passed.append('pet bottom docks to timer even when its center is far above it')

        pet.unbind_timer()
        config_mgr.config['settings']['magnetic_snap'] = False
        timer.move(900,900)
        drag(timer.label_name, QPoint(500,600))
        assert pet.pet_data['bound_timer_id'] == ''
        passed.append('disabled magnetic snap prevents automatic binding')

        I18n.set_language('zh_CN')
        settings = MainSettingWindow()
        created.append(settings)
        assert settings.tab_timer.sub_tabs.tabText(0) == I18n.tr('subtab_timer_list')
        assert settings.tab_timer.sub_tabs.tabText(1) == I18n.tr('subtab_window_groups')
        assert settings.title_bar.theme_btn.text() == '深色'
        assert '输入监控' in settings._compet_permission_label.text()
        assert settings._compet_permission_button.text() == '申请权限'
        dialog = ConfirmDialog(I18n.tr('del_group'), "'probe' 그룹을 삭제하시겠습니까?", is_danger=True)
        created.append(dialog)
        assert {button.text() for button in dialog.findChildren(QPushButton)} == {'取消','确认'}
        assert any(label.text() == '确定删除“probe”分组吗？' for label in dialog.findChildren(QLabel))
        normal = ConfirmDialog('probe','probe')
        created.append(normal)
        assert {button.text() for button in normal.findChildren(QPushButton)} == {'取消','确定'}
        I18n.set_language('en')
        assert settings.title_bar.theme_btn.text() == 'Dark'
        assert 'Input Monitoring' in settings._compet_permission_label.text()
        I18n.set_language('zh_CN')
        assert settings.title_bar.theme_btn.text() == '深色'
        passed.append('Chinese initial tabs, confirmation buttons, group deletion, and live theme label translation')
        return {'passed': passed, 'config_save_calls_intercepted':len(saves)}
    finally:
        for widget in reversed(created):
            if not sip.isdeleted(widget):
                widget.hide()
                sip.delete(widget)
        I18n.set_language(old_language)
        config_mgr.config = old_config
        config_mgr.save_config = old_save
        config_mgr.save_skin_config = old_save_skin
