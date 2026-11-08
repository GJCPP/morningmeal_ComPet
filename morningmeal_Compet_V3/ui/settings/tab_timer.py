# ui/settings/tab_timer.py
import uuid
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy,
    QPushButton, QLabel, QLineEdit, QCheckBox, QComboBox, QFrame,
    QTabWidget, QStyle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from ui.numeric_editor import SettingsSpinBox
from core.config_manager import config_mgr
from core.i18n import I18n
from core.activity_engine import activity_engine
from core.timer_policy import has_fallback_timer
from ui.timer_statistics import show_timer_statistics, display_reset_notice
from ui.components import (
    ConfirmDialog, capture_bridge,
    start_window_click_capture, cancel_window_click_capture, format_time
)

class TimerCardWidget(QFrame):
    changed = pyqtSignal()
    order_requested = pyqtSignal(str, int)
    expanded_changed = pyqtSignal(str, bool)
    name_updated = pyqtSignal(str, str)

    def __init__(self, timer_data, remove_callback, parent=None):
        super().__init__(parent)
        self.timer_data = timer_data
        self.remove_callback = remove_callback
        self._position = 1
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.update_card_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(6)
        self.position_label = QLabel()
        header.addWidget(self.position_label)
        self.expand_btn = QPushButton()
        self.expand_btn.setCheckable(True)
        self.expand_btn.setMinimumWidth(0)
        self.expand_btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.expand_btn.setStyleSheet('text-align: left; padding: 5px 6px;')
        self.expand_btn.toggled.connect(self.on_expanded_toggled)
        header.addWidget(self.expand_btn, 1)
        self.time_label = QLabel(format_time(self.timer_data.get('elapsed_seconds', 0)))
        self.time_label.setStyleSheet('font-weight: bold; font-family: monospace; font-size: 16px; color: #2563EB;')
        header.addWidget(self.time_label)
        self.move_up_btn = QPushButton()
        self.move_up_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.move_down_btn = QPushButton()
        self.move_down_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        for button, direction in ((self.move_up_btn, -1), (self.move_down_btn, 1)):
            button.setFixedSize(28, 28)
            button.setStyleSheet('padding: 0;')
            button.clicked.connect(lambda checked=False, step=direction: self.order_requested.emit(self.timer_data['id'], step))
            header.addWidget(button)
        layout.addLayout(header)

        self.details = QWidget()
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 2, 0, 2)
        details_layout.setSpacing(8)
        name_layout = QHBoxLayout()
        self.name_label = QLabel()
        name_layout.addWidget(self.name_label)
        self.name_edit = QLineEdit(self.timer_data.get('name', I18n.tr('default_timer_name')))
        self.name_edit.setMinimumWidth(0)
        self.name_edit.setFixedHeight(28)
        self.name_edit.textChanged.connect(self.on_name_text_changed)
        self.name_edit.editingFinished.connect(self.on_name_editing_finished)
        name_layout.addWidget(self.name_edit, 1)
        self.del_btn = QPushButton()
        self.del_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setStyleSheet('padding: 0; color: #EF4444;')
        self.del_btn.clicked.connect(lambda: self.remove_callback(self.timer_data))
        name_layout.addWidget(self.del_btn)
        details_layout.addLayout(name_layout)

        group_layout = QHBoxLayout()
        self.lbl_g = QLabel()
        self.group_combo = QComboBox()
        self.group_combo.setMinimumWidth(0)
        self.group_combo.setMinimumContentsLength(1)
        self.group_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.group_combo.setFixedHeight(28)
        self.refresh_groups()
        self.group_combo.currentTextChanged.connect(self.on_group_changed)
        group_layout.addWidget(self.lbl_g)
        group_layout.addWidget(self.group_combo, 1)
        details_layout.addLayout(group_layout)
        self.fallback_hint = QLabel()
        self.fallback_hint.setWordWrap(True)
        self.fallback_hint.setMinimumWidth(0)
        self.fallback_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.fallback_hint.setVisible(bool(self.timer_data.get('is_fallback', False)))
        details_layout.addWidget(self.fallback_hint)

        idle_layout = QHBoxLayout()
        self.lbl_i = QLabel()
        self.idle_spin = SettingsSpinBox()
        self.idle_spin.setRange(1, 2_147_483_647)  # Full positive QSpinBox integer range.
        self.idle_spin.setValue(self.timer_data.get('idle_timeout', 5))
        self.idle_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.idle_spin.valueChanged.connect(self.on_idle_changed)
        idle_layout.addWidget(self.lbl_i)
        idle_layout.addWidget(self.idle_spin, 1)
        self.btn_reset = QPushButton()
        self.btn_reset.setFixedHeight(28)
        self.btn_reset.clicked.connect(self.reset_time)
        idle_layout.addWidget(self.btn_reset)
        details_layout.addLayout(idle_layout)
        layout.addWidget(self.details)
        self.details.hide()
        self.retranslate_ui()
        I18n.language_changed.connect(self.retranslate_ui)

    def set_expanded(self, expanded):
        self.expand_btn.setChecked(expanded)

    def on_expanded_toggled(self, expanded):
        self.details.setVisible(expanded)
        self.update_summary()
        self.expanded_changed.emit(self.timer_data['id'], expanded)

    def update_summary(self):
        name = self.timer_data.get('name', I18n.tr('default_timer_name'))
        arrow = QStyle.StandardPixmap.SP_ArrowDown if self.expand_btn.isChecked() else QStyle.StandardPixmap.SP_ArrowRight
        self.expand_btn.setIcon(self.style().standardIcon(arrow))
        available = max(0, self.expand_btn.width() - self.expand_btn.iconSize().width() - 20)
        self.expand_btn.setText(self.expand_btn.fontMetrics().elidedText(
            name, Qt.TextElideMode.ElideRight, available))
        key = 'collapse_timer_details' if self.expand_btn.isChecked() else 'edit_timer_details'
        description = I18n.tr(key).format(name=name)
        self.expand_btn.setToolTip(description)
        self.expand_btn.setAccessibleName(description)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_summary()

    def set_order_position(self, index, count):
        self._position = index + 1
        self.position_label.setText(I18n.tr('timer_order').format(position=self._position))
        self.move_up_btn.setEnabled(index > 0)
        self.move_down_btn.setEnabled(index < count - 1)

    def update_time_display(self, seconds: int):
        self.timer_data['elapsed_seconds'] = seconds
        self.time_label.setText(format_time(seconds))

    def refresh_groups(self):
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        if self.timer_data.get('is_fallback', False):
            self.group_combo.setEnabled(False)
            self.group_combo.addItem(I18n.tr('fallback_scope'))
        else:
            groups = list(config_mgr.config.get('groups', {}).keys())
            self.group_combo.setEnabled(bool(groups))
            self.group_combo.addItems(groups or [I18n.tr('no_group_available')])
            current = self.timer_data.get('group', '')
            if current not in groups:
                current = groups[0] if groups else ''
                self.timer_data['group'] = current
            if groups:
                self.group_combo.setCurrentText(current)
        self.group_combo.blockSignals(False)

    def retranslate_ui(self):
        self.position_label.setText(I18n.tr('timer_order').format(position=self._position))
        for button, key in ((self.move_up_btn, 'move_up'), (self.move_down_btn, 'move_down'), (self.del_btn, 'del_timer_title')):
            button.setToolTip(I18n.tr(key))
            button.setAccessibleName(I18n.tr(key))
        self.name_label.setText(I18n.tr('timer_name'))
        self.name_edit.setAccessibleName(I18n.tr('timer_name'))
        self.lbl_g.setText(I18n.tr('fallback_label' if self.timer_data.get('is_fallback') else 'group_label'))
        self.fallback_hint.setText(I18n.tr('fallback_hint'))
        if self.timer_data.get('is_fallback'):
            self.refresh_groups()
        self.lbl_i.setText(I18n.tr('idle_label'))
        self.idle_spin.setSuffix(f" {I18n.tr('unit_seconds')}")
        self.idle_spin.setAccessibleName(I18n.tr('idle_label'))
        self.btn_reset.setText(I18n.tr('reset'))
        self.update_summary()

    def update_card_style(self):
        is_dark = config_mgr.config.get("settings", {}).get("dark_mode", False)
        bg = "#27272A" if is_dark else "#FFFFFF"
        border = "#3F3F46" if is_dark else "#D0D7DE"
        text_color = "#FAFAFA" if is_dark else "#111827"
        self.setStyleSheet(f"""
            TimerCardWidget {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel {{ color: {text_color}; }}
        """)

    def on_name_text_changed(self, txt):
        """타이핑 중: 데이터 업데이트 및 바탕화면 위젯 라벨 즉시 변경"""
        self.timer_data["name"] = txt
        self.update_summary()
        self.name_updated.emit(self.timer_data.get("id"), txt)

    def on_name_editing_finished(self):
        """입력 종료(엔터/포커스 아웃): 영구 저장 및 전체 동기화"""
        config_mgr.save_config()
        self.changed.emit()

    def on_group_changed(self, txt):
        if txt and txt != I18n.tr("no_group_available"):
            self.timer_data["group"] = txt
        else:
            self.timer_data["group"] = ""
        config_mgr.save_config()
        self.changed.emit()

    def on_idle_changed(self, val):
        self.timer_data["idle_timeout"] = val
        config_mgr.save_config()

    def reset_time(self):
        dlg = ConfirmDialog(I18n.tr("reset_confirm_title"), I18n.tr("reset_confirm_msg") + "\n" + display_reset_notice(), is_danger=False, parent=self)
        if dlg.exec() == ConfirmDialog.DialogCode.Accepted:
            t_id = self.timer_data.get("id")
            activity_engine.reset_timers([t_id])
            self.time_label.setText(format_time(0))
            self.changed.emit()


class GroupCardWidget(QFrame):
    rename_requested = pyqtSignal(str, str)

    def __init__(self, group_name, windows, remove_group_callback, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self.windows = list(windows) + [""] * max(0, 3 - len(windows))
        self.remove_group_callback = remove_group_callback
        self.current_capturing_btn = None
        self.update_card_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.name_edit = QLineEdit(self.group_name)
        self.name_edit.setMinimumWidth(0)
        self.name_edit.setFixedHeight(28)
        self.name_edit.setStyleSheet('font-weight: 600;')
        self.name_edit.editingFinished.connect(
            lambda: self.rename_requested.emit(self.group_name, self.name_edit.text()))
        header.addWidget(self.name_edit, 1)

        self.del_btn = QPushButton(I18n.tr("del_group"))
        self.del_btn.setFixedHeight(24)
        self.del_btn.setStyleSheet("QPushButton { font-size: 11px; padding: 2px 8px; color: #EF4444; } QPushButton:hover { background-color: #EF4444; color: white; }")
        self.del_btn.clicked.connect(lambda: self.remove_group_callback(self.group_name))
        header.addWidget(self.del_btn)
        layout.addLayout(header)
        self.name_error_label = QLabel()
        self.name_error_label.setWordWrap(True)
        self.name_error_label.setStyleSheet('color: #EF4444;')
        self.name_error_label.hide()
        layout.addWidget(self.name_error_label)
        self.name_edit.textEdited.connect(lambda: self.name_error_label.hide())

        self.slot_labels = []
        self.slot_edits = []
        self.slot_pick_btns = []
        self.slot_clear_btns = []

        self.slots_layout = QVBoxLayout()
        layout.addLayout(self.slots_layout)
        for value in self.windows:
            self.append_slot(value)
        self.add_window_btn = QPushButton(I18n.tr("add_tracked_window"))
        self.add_window_btn.clicked.connect(self.add_window)
        layout.addWidget(self.add_window_btn)

        capture_bridge.window_captured.connect(self.on_window_captured)
        self.retranslate_ui()

    def show_name_error(self, key):
        self.name_edit.setText(self.group_name)
        self.name_error_label.setProperty('translationKey', key)
        self.name_error_label.setText(I18n.tr(key))
        self.name_error_label.show()

    def append_slot(self, value=""):
        i = len(self.slot_edits)
        slot_h = QHBoxLayout()
        slot_label = QLabel(f"{I18n.tr('slot')} {i+1}:")
        slot_label.setFixedWidth(46)
        slot_label.setStyleSheet("color: #64748B; font-size: 11px;")
        self.slot_labels.append(slot_label)

        le = QLineEdit(value)
        le.setFixedHeight(28)
        le.setPlaceholderText(I18n.tr("slot_placeholder"))
        le.textChanged.connect(lambda txt, idx=i: self.on_text_changed(idx, txt))
        self.slot_edits.append(le)

        btn_p = QPushButton(I18n.tr("pick_window"))
        btn_p.setFixedHeight(28)
        btn_p.setFixedWidth(106)
        btn_p.clicked.connect(lambda _, b=btn_p, edit=le, idx=i: self.start_capture(b, edit, idx))
        self.slot_pick_btns.append(btn_p)

        btn_c = QPushButton(I18n.tr("clear"))
        btn_c.setFixedHeight(28)
        btn_c.setFixedWidth(54)
        btn_c.clicked.connect(lambda _, edit=le, idx=i: self.clear_slot(edit, idx))
        self.slot_clear_btns.append(btn_c)

        slot_h.addWidget(slot_label)
        slot_h.addWidget(le, 1)
        slot_h.addWidget(btn_p)
        slot_h.addWidget(btn_c)
        self.slots_layout.addLayout(slot_h)

    def add_window(self):
        self.windows.append("")
        self.append_slot()
        self.slot_edits[-1].setFocus()

    def retranslate_ui(self):
        self.name_edit.setAccessibleName(I18n.tr('group_name'))
        self.name_edit.setToolTip(I18n.tr('rename_group_hint'))
        error_key = self.name_error_label.property('translationKey')
        if error_key:
            self.name_error_label.setText(I18n.tr(error_key))
        self.del_btn.setText(I18n.tr("del_group"))
        self.add_window_btn.setText(I18n.tr("add_tracked_window"))
        for i, lbl in enumerate(self.slot_labels):
            lbl.setText(f"{I18n.tr('slot')} {i+1}:")
        for le in self.slot_edits:
            le.setPlaceholderText(I18n.tr("slot_placeholder"))
        for btn in self.slot_pick_btns:
            if not getattr(btn, 'is_capturing', False):
                btn.setText(I18n.tr("pick_window"))
            else:
                btn.setText(I18n.tr("waiting_click"))
        for btn in self.slot_clear_btns:
            btn.setText(I18n.tr("clear"))

    def update_card_style(self):
        is_dark = config_mgr.config.get("settings", {}).get("dark_mode", False)
        bg = "#27272A" if is_dark else "#FFFFFF"
        border = "#3F3F46" if is_dark else "#D0D7DE"
        text_color = "#FAFAFA" if is_dark else "#111827"
        self.setStyleSheet(f"""
            GroupCardWidget {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QLabel {{ color: {text_color}; }}
        """)

    def on_text_changed(self, idx, txt):
        self.windows[idx] = txt.strip()
        config_mgr.config.setdefault("groups", {})[self.group_name] = [w for w in self.windows if w]
        config_mgr.save_config()

    def clear_slot(self, le, idx):
        le.clear()
        self.on_text_changed(idx, "")

    def start_capture(self, btn, le, idx):
        if getattr(btn, 'is_capturing', False):
            self.reset_btn(btn)
            cancel_window_click_capture()
            return

        if self.current_capturing_btn:
            self.reset_btn(self.current_capturing_btn)

        self.current_capturing_btn = btn
        self.current_target = (le, idx)
        btn.is_capturing = True
        btn.setText(I18n.tr("waiting_click"))
        btn.setProperty("activeCapture", True)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        start_window_click_capture()

    def on_window_captured(self, title):
        if self.current_capturing_btn and hasattr(self, 'current_target'):
            le, idx = self.current_target
            le.setText(title)
            self.on_text_changed(idx, title)
            self.reset_btn(self.current_capturing_btn)
            self.current_capturing_btn = None

    def reset_btn(self, btn):
        btn.is_capturing = False
        btn.setText(I18n.tr("pick_window"))
        btn.setProperty("activeCapture", False)
        btn.style().unpolish(btn)
        btn.style().polish(btn)


class TabTimerSettings(QWidget):
    settings_changed = pyqtSignal()
    timer_name_changed = pyqtSignal(str, str)  # (timer_id, new_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.card_map = {}  # {timer_id: TimerCardWidget}
        timers = config_mgr.config.get('timers', [])
        self._expanded_timer_id = timers[0]['id'] if timers else None
        self.init_ui()
        
        # 엔진의 실시간 초 틱 시그널 연결 (설정 화면 초 연동)
        activity_engine.tick.connect(self.on_activity_tick)
        I18n.language_changed.connect(self.retranslate_ui)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 8, 4, 4)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.setObjectName("subTabWidget")

        # 1. 타이머 목록 탭
        self.sub_page_timers = QWidget()
        layout_timers = QVBoxLayout(self.sub_page_timers)
        layout_timers.setContentsMargins(10, 10, 10, 10)
        layout_timers.setSpacing(10)

        top_bar = QHBoxLayout()
        self.snap_cb = QCheckBox(I18n.tr("magnetic_snap"))
        self.snap_cb.setChecked(config_mgr.config.get("settings", {}).get("magnetic_snap", True))
        self.snap_cb.toggled.connect(self.on_snap_toggled)
        self.btn_add_timer = QPushButton(I18n.tr("add_timer"))
        self.btn_add_timer.clicked.connect(self.add_timer)
        top_bar.addWidget(self.snap_cb)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_add_timer)
        layout_timers.addLayout(top_bar)
        self.btn_add_fallback = QPushButton(I18n.tr("add_other_timer"))
        self.btn_add_fallback.clicked.connect(self.add_fallback_timer)
        actions = QHBoxLayout()
        actions.addWidget(self.btn_add_fallback)
        actions.addStretch()
        self.btn_statistics = QPushButton(I18n.tr("time_distribution"))
        self.btn_statistics.clicked.connect(show_timer_statistics)
        actions.addWidget(self.btn_statistics)
        self.btn_reset_all = QPushButton(I18n.tr("reset_all_timers"))
        self.btn_reset_all.setObjectName("dangerBtn")
        self.btn_reset_all.clicked.connect(self.reset_all_timers)
        actions.addWidget(self.btn_reset_all)
        layout_timers.addLayout(actions)

        self.timer_scroll = QScrollArea()
        self.timer_scroll.setWidgetResizable(True)
        self.timer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        t_content = QWidget()
        t_content.setMinimumWidth(0)
        self.timer_list_layout = QVBoxLayout(t_content)
        self.timer_list_layout.setContentsMargins(4, 4, 4, 4)
        self.timer_list_layout.setSpacing(8)
        self.timer_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.timer_scroll.setWidget(t_content)
        layout_timers.addWidget(self.timer_scroll)

        # 2. 창 그룹 관리 탭
        self.sub_page_groups = QWidget()
        layout_groups = QVBoxLayout(self.sub_page_groups)
        layout_groups.setContentsMargins(10, 10, 10, 10)
        layout_groups.setSpacing(10)

        g_header = QHBoxLayout()
        self.btn_create_g = QPushButton(I18n.tr("create_group"))
        self.btn_create_g.clicked.connect(self.create_group)
        g_header.addStretch()
        g_header.addWidget(self.btn_create_g)
        layout_groups.addLayout(g_header)

        self.group_scroll = QScrollArea()
        self.group_scroll.setWidgetResizable(True)
        g_content = QWidget()
        self.group_list_layout = QVBoxLayout(g_content)
        self.group_list_layout.setContentsMargins(4, 4, 4, 4)
        self.group_list_layout.setSpacing(10)
        self.group_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.group_scroll.setWidget(g_content)
        layout_groups.addWidget(self.group_scroll)

        self.sub_tabs.addTab(self.sub_page_timers, "타이머 목록")
        self.sub_tabs.addTab(self.sub_page_groups, "창 매칭 그룹")

        main_layout.addWidget(self.sub_tabs)

        self.refresh_timer_list()
        self.refresh_group_list()

    def on_activity_tick(self, updated_dict: dict):
        """엔진에서 1초마다 보내주는 초 데이터를 카드 위젯에 즉시 전달"""
        for t_id, secs in updated_dict.items():
            if t_id in self.card_map:
                self.card_map[t_id].update_time_display(secs)

    def on_snap_toggled(self, checked):
        config_mgr.config.setdefault("settings", {})["magnetic_snap"] = checked
        config_mgr.save_config()

    def move_timer(self, timer_id, direction):
        if direction not in (-1, 1):
            return
        timers = config_mgr.config.get("timers", [])
        index = next((i for i, timer in enumerate(timers) if timer['id'] == timer_id), None)
        if index is None or not 0 <= index + direction < len(timers):
            return
        target = index + direction
        timers[index], timers[target] = timers[target], timers[index]
        config_mgr.save_config()
        self.refresh_timer_list()
        self.settings_changed.emit()

    def reset_all_timers(self):
        timers = config_mgr.config.get("timers", [])
        if not timers:
            return
        dialog = ConfirmDialog(I18n.tr("reset_all_title"),
            I18n.tr("reset_all_message").format(count=len(timers)) + "\n" + display_reset_notice(), is_danger=True, parent=self)
        if dialog.exec() == ConfirmDialog.DialogCode.Accepted:
            activity_engine.reset_timers()
            self.settings_changed.emit()

    def add_timer(self):
        self._add_timer(False)

    def add_fallback_timer(self):
        if not has_fallback_timer(config_mgr.config):
            self._add_timer(True)

    def _add_timer(self, fallback):
        groups = list(config_mgr.config.get("groups", {}).keys())
        first_g = groups[0] if groups else ""
        new_t = {
            "id": str(uuid.uuid4()),
            "name": I18n.tr("other_timer_name") if fallback else f"{I18n.tr('default_timer_name')} {len(config_mgr.config.get('timers', [])) + 1}",
            "group": "" if fallback else first_g,
            "is_fallback": fallback,
            "idle_timeout": 5,
            "elapsed_seconds": 0,
            "x": 200, "y": 300,
            "paused": False
        }
        self._expanded_timer_id = new_t["id"]
        config_mgr.config.setdefault("timers", []).append(new_t)
        config_mgr.save_config()
        self.refresh_timer_list()
        self.settings_changed.emit()

    def remove_timer(self, timer_data):
        dlg = ConfirmDialog(I18n.tr("del_timer_title"), I18n.tr("del_timer_msg").format(name=timer_data.get('name')), is_danger=True, parent=self)
        if dlg.exec() == ConfirmDialog.DialogCode.Accepted:
            t_id = timer_data.get("id")
            for p in config_mgr.config.get("pets", []):
                if p.get("bound_timer_id") == t_id:
                    p["bound_timer_id"] = ""
            if timer_data in config_mgr.config.get("timers", []):
                config_mgr.config["timers"].remove(timer_data)
            config_mgr.save_config()
            self.refresh_timer_list()
            self.settings_changed.emit()

    def create_group(self):
        groups = config_mgr.config.setdefault('groups', {})
        index = 1
        while f"{I18n.tr('default_group_name')} {index}" in groups:
            index += 1
        name = f"{I18n.tr('default_group_name')} {index}"
        groups[name] = ['', '', '']
        config_mgr.save_config()
        self.refresh_group_list()
        self.refresh_timer_list()
        self.settings_changed.emit()
        QTimer.singleShot(0, lambda: self.focus_group_name(name))

    def focus_group_name(self, name):
        for index in range(self.group_list_layout.count()):
            card = self.group_list_layout.itemAt(index).widget()
            if card.group_name == name:
                self.group_scroll.ensureWidgetVisible(card, 0, 8)
                card.name_edit.setFocus()
                card.name_edit.selectAll()
                break

    def rename_group(self, old_name, new_name):
        groups = config_mgr.config.get('groups', {})
        if old_name not in groups:
            return
        card = next((self.group_list_layout.itemAt(index).widget()
                     for index in range(self.group_list_layout.count())
                     if self.group_list_layout.itemAt(index).widget().group_name == old_name), None)
        if card is None:
            return
        new_name = new_name.strip()
        if not new_name:
            card.show_name_error('group_name_empty')
            return
        if new_name != old_name and new_name in groups:
            card.show_name_error('group_exists_warn')
            return
        card.name_edit.setText(new_name)
        card.name_error_label.hide()
        if new_name == old_name:
            return
        # Rename in place without moving groups, rebuilding editors or losing capture state.
        renamed = {new_name if name == old_name else name: windows
                   for name, windows in groups.items()}
        groups.clear()
        groups.update(renamed)
        card.group_name = new_name
        for timer in config_mgr.config.get('timers', []):
            if timer.get('group') == old_name:
                timer['group'] = new_name
        config_mgr.save_config()
        self.refresh_timer_list()
        self.settings_changed.emit()

    def remove_group(self, name):
        dlg = ConfirmDialog(I18n.tr("del_group"), f"'{name}' 그룹을 삭제하시겠습니까?", is_danger=True, parent=self)
        if dlg.exec() != ConfirmDialog.DialogCode.Accepted: return
        groups = config_mgr.config.get("groups", {})
        if name in groups: del groups[name]
        fallback = list(groups.keys())[0] if groups else ""
        for t in config_mgr.config.get("timers", []):
            if t.get("group") == name: t["group"] = fallback
        config_mgr.save_config()
        self.refresh_group_list()
        self.refresh_timer_list()
        self.settings_changed.emit()

    def on_card_expanded(self, timer_id, expanded):
        if expanded:
            self._expanded_timer_id = timer_id
            for other_id, card in self.card_map.items():
                if other_id != timer_id:
                    card.set_expanded(False)
            QTimer.singleShot(0, lambda: self.ensure_timer_visible(timer_id))
        elif self._expanded_timer_id == timer_id:
            self._expanded_timer_id = None

    def ensure_timer_visible(self, timer_id):
        card = self.card_map.get(timer_id)
        if card is not None and card.expand_btn.isChecked():
            self.timer_scroll.ensureWidgetVisible(card, 0, 8)

    def refresh_timer_list(self):
        timers = config_mgr.config.get('timers', [])
        self.btn_add_fallback.setEnabled(not has_fallback_timer(config_mgr.config))
        self.btn_reset_all.setEnabled(bool(timers))
        alive = {timer['id'] for timer in timers}
        for timer_id in list(self.card_map):
            if timer_id not in alive:
                card = self.card_map.pop(timer_id)
                self.timer_list_layout.removeWidget(card)
                card.hide()
                card.deleteLater()
        if self._expanded_timer_id not in alive:
            self._expanded_timer_id = None

        # Move existing rows in place: rebuilding destroys editor focus and state.
        for index, timer in enumerate(timers):
            timer_id = timer['id']
            card = self.card_map.get(timer_id)
            if card is None:
                card = TimerCardWidget(timer, self.remove_timer)
                card.order_requested.connect(self.move_timer)
                card.expanded_changed.connect(self.on_card_expanded)
                card.changed.connect(self.settings_changed.emit)
                card.name_updated.connect(self.timer_name_changed.emit)
                self.card_map[timer_id] = card
            else:
                card.timer_data = timer
                card.refresh_groups()
                card.update_time_display(timer.get('elapsed_seconds', 0))
                if not card.name_edit.hasFocus() and card.name_edit.text() != timer.get('name', ''):
                    card.name_edit.blockSignals(True)
                    card.name_edit.setText(timer.get('name', ''))
                    card.name_edit.blockSignals(False)
                card.update_summary()
            card.set_order_position(index, len(timers))
            if self.timer_list_layout.indexOf(card) != index:
                self.timer_list_layout.removeWidget(card)
                self.timer_list_layout.insertWidget(index, card)
            card.set_expanded(timer_id == self._expanded_timer_id)

    def refresh_group_list(self):
        groups = config_mgr.config.get('groups', {})
        existing = {self.group_list_layout.itemAt(index).widget().group_name:
                    self.group_list_layout.itemAt(index).widget()
                    for index in range(self.group_list_layout.count())}
        for name, card in existing.items():
            if name not in groups:
                self.group_list_layout.removeWidget(card)
                card.hide()
                card.deleteLater()
        for index, (name, windows) in enumerate(groups.items()):
            card = existing.get(name)
            if card is None:
                card = GroupCardWidget(name, windows, self.remove_group)
                card.rename_requested.connect(self.rename_group)
            if self.group_list_layout.indexOf(card) != index:
                self.group_list_layout.removeWidget(card)
                self.group_list_layout.insertWidget(index, card)

    def retranslate_ui(self):
        self.sub_tabs.setTabText(0, I18n.tr("subtab_timer_list"))
        self.sub_tabs.setTabText(1, I18n.tr("subtab_window_groups"))
        
        self.snap_cb.setText(I18n.tr("magnetic_snap"))
        self.btn_add_timer.setText(I18n.tr("add_timer"))
        self.btn_add_fallback.setText(I18n.tr("add_other_timer"))
        self.btn_statistics.setText(I18n.tr("time_distribution"))
        self.btn_reset_all.setText(I18n.tr("reset_all_timers"))
        self.btn_create_g.setText(I18n.tr("create_group"))

        for card in self.card_map.values():
            card.retranslate_ui()

        for i in range(self.group_list_layout.count()):
            w = self.group_list_layout.itemAt(i).widget()
            if isinstance(w, GroupCardWidget):
                w.retranslate_ui()

    def apply_theme(self):
        for card in self.card_map.values():
            card.update_card_style()

        for i in range(self.group_list_layout.count()):
            w = self.group_list_layout.itemAt(i).widget()
            if isinstance(w, GroupCardWidget):
                w.update_card_style()