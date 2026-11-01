"""Shared interaction/localization fixes for source builds and repaired release bundles."""
import re
from PyQt6.QtCore import QObject, QEvent, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
from core.config_manager import config_mgr
from core.docking import docking_score, snap_timer_rect, timer_position_below_pet
from core.i18n import I18n, TRANSLATIONS
from core.snap_manager import SnapManager
from ui.pet_widget import PetWidget
from ui.timer_widget import TimerWidget
from ui.components import ConfirmDialog
from ui.settings.main_window import MainSettingWindow
from ui.settings.tab_timer import TabTimerSettings

_INSTALLED = False
_TRANSLATIONS = {
    'ko': dict(cancel='취소', confirm='확인', execute='실행', theme_dark='다크', theme_light='라이트', delete_group_confirm="'{name}' 그룹을 삭제하시겠습니까?"),
    'en': dict(cancel='Cancel', confirm='OK', execute='Confirm', theme_dark='Dark', theme_light='Light', delete_group_confirm="Delete the group '{name}'?"),
    'ja': dict(cancel='キャンセル', confirm='確認', execute='実行', theme_dark='ダーク', theme_light='ライト', delete_group_confirm="グループ「{name}」を削除しますか？"),
    'zh_CN': dict(cancel='取消', confirm='确定', execute='确认', theme_dark='深色', theme_light='浅色', delete_group_confirm='确定删除“{name}”分组吗？'),
    'zh_TW': dict(cancel='取消', confirm='確定', execute='確認', theme_dark='深色', theme_light='淺色', delete_group_confirm='確定刪除「{name}」群組嗎？'),
}


def _settings():
    return config_mgr.config.get('settings', {})


def _distance():
    return max(0, int(_settings().get('snap_distance', 15)))


def _rect(widget, position=None):
    pos = position if position is not None else widget.pos()
    return pos.x(), pos.y(), widget.width(), widget.height()


def _visible_pets():
    return [widget for widget in QApplication.topLevelWidgets()
            if isinstance(widget, PetWidget) and widget.isVisible()]


def _timer_snap(moving_widget, all_widgets, new_pos):
    if not _settings().get('magnetic_snap', True):
        return new_pos
    others = [_rect(widget) for widget in all_widgets
              if widget is not moving_widget and widget.isVisible()]
    x, y = snap_timer_rect(_rect(moving_widget, new_pos), others, _distance())
    return QPoint(x, y)


def _pet_for_timer(timer, position):
    if not _settings().get('magnetic_snap', True):
        return None
    if timer.get_bound_pet_callback(timer.timer_data.get('id')) is not None:
        return None
    candidates = []
    for pet in _visible_pets():
        if pet.pet_data.get('bound_timer_id'):
            continue
        score = docking_score(_rect(pet), _rect(timer, position), _distance())
        if score is not None:
            candidates.append((score, pet))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _move_timer(timer, raw_position):
    pet = _pet_for_timer(timer, raw_position)
    if pet is not None:
        x, y = timer_position_below_pet(_rect(pet), (timer.width(), timer.height()))
        position = QPoint(x, y)
    else:
        position = _timer_snap(timer, timer.get_all_timers_callback(), raw_position)
    timer.move(position)
    bound = timer.get_bound_pet_callback(timer.timer_data.get('id'))
    if bound is not None:
        bound.snap_to_timer(timer)
    timer.moved.emit(timer.timer_data.get('id'), position.x(), position.y())


def _finish_timer_drag(timer):
    timer.timer_data.update(x=timer.x(), y=timer.y())
    bound = timer.get_bound_pet_callback(timer.timer_data.get('id'))
    if bound is not None:
        bound.save_position()
    else:
        pet = _pet_for_timer(timer, timer.pos())
        if pet is not None:
            pet.bind_to_timer(timer.timer_data.get('id'))
        else:
            config_mgr.save_config()


class _TimerDragFilter(QObject):
    """Handle the entire timer card, including its labels, as one drag surface."""
    def __init__(self, timer):
        super().__init__(timer)
        self.timer = timer
        self.offset = None
        self.press_position = None
        self.dragging = False

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.globalPosition().toPoint()
            self.offset = self.press_position - self.timer.pos()
            self.dragging = False
            self.timer.grabMouse()
            event.accept()
            return True
        if kind == QEvent.Type.MouseMove and self.offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            cursor = event.globalPosition().toPoint()
            if (cursor - self.press_position).manhattanLength() >= QApplication.startDragDistance():
                self.dragging = True
            if self.dragging:
                _move_timer(self.timer, cursor - self.offset)
            event.accept()
            return True
        if kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton and self.offset is not None:
            if self.dragging:
                _finish_timer_drag(self.timer)
            self.offset = self.press_position = None
            self.dragging = False
            self.timer.releaseMouse()
            event.accept()
            return True
        if kind == QEvent.Type.UngrabMouse:
            self.offset = self.press_position = None
            self.dragging = False
        return False


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    for language, values in _TRANSLATIONS.items():
        TRANSLATIONS[language].update(values)

    original_dialog_init = ConfirmDialog.__init__
    def dialog_init(self, title_text, msg_text, is_danger=False, parent=None):
        match = re.fullmatch(r"'(.*)' 그룹을 삭제하시겠습니까\?", msg_text, re.DOTALL)
        if title_text == I18n.tr('del_group') and match:
            msg_text = I18n.tr('delete_group_confirm').format(name=match.group(1))
        original_dialog_init(self, title_text, msg_text, is_danger=is_danger, parent=parent)
        for button in self.findChildren(QPushButton):
            if button.text() in ('취소', 'Cancel'):
                button.setText(I18n.tr('cancel'))
            elif button.text() in ('실행', '확인', 'OK'):
                button.setText(I18n.tr('execute' if is_danger else 'confirm'))
    ConfirmDialog.__init__ = dialog_init

    original_tabs_init = TabTimerSettings.__init__
    def tabs_init(self, *args, **kwargs):
        original_tabs_init(self, *args, **kwargs)
        self.retranslate_ui()
    TabTimerSettings.__init__ = tabs_init

    def theme_text(self):
        self.title_bar.theme_btn.setText(I18n.tr('theme_light' if self.is_dark else 'theme_dark'))
    original_theme = MainSettingWindow.apply_theme
    def apply_theme(self):
        original_theme(self)
        theme_text(self)
    MainSettingWindow.apply_theme = apply_theme
    original_retranslate = MainSettingWindow.retranslate_ui
    def retranslate(self):
        original_retranslate(self)
        theme_text(self)
    MainSettingWindow.retranslate_ui = retranslate

    original_timer_init = TimerWidget.__init__
    def timer_init(self, *args, **kwargs):
        original_timer_init(self, *args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._compet_drag_filter = _TimerDragFilter(self)
        self.installEventFilter(self._compet_drag_filter)
        for label in self.findChildren(QLabel):
            label.installEventFilter(self._compet_drag_filter)
    TimerWidget.__init__ = timer_init
    SnapManager.calculate_snap = staticmethod(_timer_snap)

    original_pet_release = PetWidget.mouseReleaseEvent
    def pet_release(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        if self.pet_data.get('bound_timer_id'):
            original_pet_release(self, event)
            return
        candidates = []
        if _settings().get('magnetic_snap', True):
            for timer in self.get_all_timers_callback():
                if not timer.isVisible():
                    continue
                if any(pet is not self and pet.pet_data.get('bound_timer_id') == timer.timer_data.get('id') for pet in _visible_pets()):
                    continue
                score = docking_score(_rect(self), _rect(timer), _distance())
                if score is not None:
                    candidates.append((score, timer))
        if candidates:
            timer = min(candidates, key=lambda item: item[0])[1]
            self.bind_to_timer(timer.timer_data.get('id'))
        else:
            self.save_position()
        event.accept()
    PetWidget.mouseReleaseEvent = pet_release
    _INSTALLED = True
