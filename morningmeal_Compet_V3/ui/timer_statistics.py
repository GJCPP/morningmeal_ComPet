"""Live, read-only pie chart of every timer, without extra chart dependencies."""
import math
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import Qt, QDate, QRectF, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QStyleFactory,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from core.config_manager import config_mgr, BUNDLE_DIR
from core.i18n import I18n
from core.timer_statistics import timer_distribution
from core.timer_history import get_history_store, statistics_day, period_bounds
from ui.components import format_time


_HISTORY_TEXT = {
    'zh_CN': ('当前显示','日','周','月','当前统计日','已删除','每日 06:00 换日；跟随电脑时区。清零只影响当前显示。多个计时器重叠累计时，总和可能超过实际经过时间。','历史从功能启用时开始记录，旧累计不回填；无记录日期按零展示。'),
    'zh_TW': ('目前顯示','日','週','月','目前統計日','已刪除','每日 06:00 換日，跟隨電腦時區；歸零不刪除歷史。重疊計時的總和可能超過實際時間。','歷史從功能啟用時開始；舊累計不回填，無紀錄日期以零顯示。'),
    'en': ('Display','Day','Week','Month','Current day','Deleted','Days start at 06:00 in the computer time zone. Reset affects display only. Overlapping timers may exceed wall time.','History starts when enabled; old totals are not backfilled. Dates without records show zero.'),
    'ja': ('現在の表示','日','週','月','現在の集計日','削除済み','端末のタイムゾーンで毎日06:00に日付を区切ります。リセットは表示のみ。重複計測の合計は実時間を超える場合があります。','履歴は機能の有効化時から記録します。以前の合計は振り分けず、記録のない日はゼロで表示します。'),
    'ko': ('현재 표시','일','주','월','현재 집계일','삭제됨','컴퓨터 시간대의 매일 06:00에 집계일이 바뀝니다. 초기화는 표시에만 적용됩니다. 중복 타이머 합계는 실제 시간을 초과할 수 있습니다.','기능 활성화 이후부터 기록합니다. 기존 합계는 소급하지 않으며 기록 없는 날짜는 0으로 표시됩니다.'),
}


def history_text():
    return _HISTORY_TEXT.get(I18n.get_lang(), _HISTORY_TEXT['en'])


def display_reset_notice():
    return {
        'zh_CN':'只清零前台显示，历史统计保留。',
        'zh_TW':'僅歸零目前顯示，歷史統計保留。',
        'en':'Only display counters are reset. History is retained.',
        'ja':'表示のみをリセットし、履歴は保持します。',
        'ko':'표시만 초기화하며 기록은 유지합니다.',
    }.get(I18n.get_lang(),'Only display counters are reset. History is retained.')


COLORS = ['#2563EB', '#F97316', '#10B981', '#A855F7', '#EC4899',
          '#06B6D4', '#EAB308', '#6366F1', '#EF4444', '#14B8A6']


class TimerPieChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.total = 0
        self.setMinimumSize(200, 200)
        self.setMaximumHeight(320)
        self.setMouseTracking(True)
        self.setAccessibleName(I18n.tr('time_distribution'))

    def set_data(self, rows, total):
        self.rows, self.total = rows, total
        self.setAccessibleName(I18n.tr('time_distribution'))
        self.update()

    def pie_rect(self):
        side = max(0, min(self.width(), self.height()) - 20)
        return QRectF((self.width()-side)/2, (self.height()-side)/2, side, side)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = config_mgr.config.get('settings', {}).get('dark_mode', False)
        rect = self.pie_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        if not self.total:
            painter.setBrush(QColor('#3F3F46' if dark else '#E5E7EB'))
            painter.drawEllipse(rect)
            painter.setPen(QColor('#FAFAFA' if dark else '#4B5563'))
            painter.drawText(rect.adjusted(20, 20, -20, -20),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             I18n.tr('stats_empty'))
            return
        painter.setPen(QPen(QColor('#18181B' if dark else '#FFFFFF'), 2))
        used = 0
        cumulative = 0.0
        for index, row in enumerate(self.rows):
            cumulative += row['share']
            end = round(cumulative * 5760)
            span = end - used
            if row['seconds'] and span:
                painter.setBrush(QColor(COLORS[index % len(COLORS)]))
                painter.drawPie(rect, 1440 + used, span)
            used = end

    def mouseMoveEvent(self, event):
        rect = self.pie_rect()
        dx, dy = event.position().x()-rect.center().x(), event.position().y()-rect.center().y()
        if not self.total or math.hypot(dx, dy) > rect.width()/2:
            self.setToolTip('')
            return
        angle = (math.degrees(math.atan2(-dy, dx))-90) % 360
        cumulative = 0
        for row in self.rows:
            cumulative += row['share'] * 360
            if angle < cumulative:
                name = row['name'] or I18n.tr('default_timer_name')
                self.setToolTip(f"{name}: {format_time(row['seconds'])} ({row['share']:.1%})")
                return


class TimerStatisticsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName('timerStatisticsDialog')
        self.resize(560, 660)
        self.setMinimumSize(460, 560)
        self._last_snapshot = None
        self._dark = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(9)
        self.title_label = QLabel()
        self.title_label.setStyleSheet('font-size: 19px; font-weight: 600;')
        layout.addWidget(self.title_label)
        self.total_label = QLabel()
        self.total_label.setStyleSheet('font-size: 15px; font-weight: 600;')
        layout.addWidget(self.total_label)
        controls = QHBoxLayout()
        self.period_combo = QComboBox()
        for key in ('display','day','week','month'):
            self.period_combo.addItem(key,key)
        self.previous_button = QPushButton('‹')
        self.next_button = QPushButton('›')
        self.today_button = QPushButton()
        self.date_edit = QDateEdit()
        # Native Aqua controls can inherit the OS dark palette while this
        # dialog uses a light stylesheet. Style these controls consistently.
        self._control_style = QStyleFactory.create('Fusion')
        self._control_style.setParent(self)
        self.period_combo.setStyle(self._control_style)
        self.date_edit.setStyle(self._control_style)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.calendarWidget().setStyle(self._control_style)
        self.period_combo.setMinimumWidth(100)
        self.date_edit.setMinimumWidth(140)
        for button in (self.previous_button,self.next_button):
            button.setFixedWidth(32)
            button.setObjectName('statsPeriodNav')
        for control in (self.period_combo,self.date_edit):
            control.setMinimumHeight(30)
        self.date_edit.setDisplayFormat('yyyy-MM-dd')
        self.date_edit.setDate(QDate.fromString(statistics_day().isoformat(),'yyyy-MM-dd'))
        for widget in (self.period_combo,self.previous_button,self.date_edit,self.next_button,self.today_button):
            controls.addWidget(widget)
        layout.addLayout(controls)
        self._follow_today = True
        self.period_combo.currentIndexChanged.connect(self.refresh)
        self.date_edit.dateChanged.connect(self.date_selected)
        self.previous_button.clicked.connect(lambda:self.navigate(-1))
        self.next_button.clicked.connect(lambda:self.navigate(1))
        self.today_button.clicked.connect(self.go_today)
        self.range_label = QLabel()
        self.range_label.setWordWrap(True)
        layout.addWidget(self.range_label)
        self.chart = TimerPieChart()
        layout.addWidget(self.chart, 1)
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)
        self.table = QTableWidget(0, 3)
        self.table.setMinimumHeight(110)
        self.table.setMaximumHeight(200)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignRight)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh)
        I18n.language_changed.connect(self.refresh)
        self.refresh()

    def date_selected(self):
        self._follow_today = False
        self.refresh()

    def go_today(self):
        self.date_edit.setDate(QDate.fromString(statistics_day().isoformat(),'yyyy-MM-dd'))
        self._follow_today = True
        self.refresh()

    def navigate(self, direction):
        kind = self.period_combo.currentData()
        selected = self.date_edit.date()
        self.date_edit.setDate(selected.addMonths(direction) if kind=='month'
            else selected.addDays(direction * (7 if kind=='week' else 1)))

    def refresh(self):
        if self._follow_today:
            self.date_edit.blockSignals(True)
            self.date_edit.setDate(QDate.fromString(statistics_day().isoformat(),'yyyy-MM-dd'))
            self.date_edit.blockSignals(False)
        mode = self.period_combo.currentData()
        words = history_text()
        for index in range(4):
            self.period_combo.setItemText(index,words[index])
        self.today_button.setText(words[4])
        for widget in (self.previous_button,self.next_button,self.date_edit,self.today_button):
            widget.setEnabled(mode!='display')
        if mode=='display':
            self.date_edit.lineEdit().deselect()
        day = date.fromisoformat(self.date_edit.date().toString('yyyy-MM-dd'))
        if mode=='display':
            rows, total = timer_distribution(config_mgr.config.get('timers', []))
            period_label = words[0]
        else:
            rows,total = get_history_store().distribution(day,mode)
            rows = [dict(row,name=row['name'] + (' ('+words[5]+')' if row['deleted'] else '')) for row in rows]
            start,end = period_bounds(day,mode)
            period_label = f'{start.isoformat()} 06:00 → {end.isoformat()} 06:00'
        self.range_label.setText(period_label)
        dark = config_mgr.config.get('settings', {}).get('dark_mode', False)
        history_error = bool(get_history_store().last_error) if mode!='display' else False
        snapshot = (history_error,mode,day,tuple((row['id'], row['name'], row['seconds']) for row in rows), I18n.get_lang(), dark)
        if snapshot == self._last_snapshot:
            return
        self._last_snapshot = snapshot
        if self._dark != dark:
            self._dark = dark
            bg, fg, border = ('#18181B', '#FAFAFA', '#3F3F46') if dark else ('#FFFFFF', '#111827', '#D1D5DB')
            disabled = '#A1A1AA' if dark else '#6B7280'
            arrow = (Path(BUNDLE_DIR)/'assets/icons/chevron-down.svg').as_posix()
            for control in (self.period_combo,self.date_edit,self.date_edit.calendarWidget()):
                palette = QPalette(control.palette())
                for group in (QPalette.ColorGroup.Active,QPalette.ColorGroup.Inactive,QPalette.ColorGroup.Disabled):
                    color = disabled if group==QPalette.ColorGroup.Disabled else fg
                    for role in (QPalette.ColorRole.Text,QPalette.ColorRole.WindowText,QPalette.ColorRole.ButtonText):
                        palette.setColor(group,role,QColor(color))
                    for role in (QPalette.ColorRole.Base,QPalette.ColorRole.Window,QPalette.ColorRole.Button):
                        palette.setColor(group,role,QColor(bg))
                    palette.setColor(group,QPalette.ColorRole.Highlight,QColor('#2563EB'))
                    palette.setColor(group,QPalette.ColorRole.HighlightedText,QColor('#FFFFFF'))
                control.setPalette(palette)
            self.setStyleSheet(f"""
                QDialog#timerStatisticsDialog {{ background: {bg}; }}
                QLabel {{ color: {fg}; }}
                QComboBox, QDateEdit {{ background: {bg}; color: {fg}; border: 1px solid {border};
                    border-radius: 5px; padding: 4px 6px; font-size: 13px; font-weight: normal; }}
                QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 20px; }}
                QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{arrow}"); width: 12px; height: 12px; }}
                QComboBox:disabled, QDateEdit:disabled {{ color: {disabled}; }}
                QDateEdit QLineEdit {{ background: transparent; color: {fg}; border: none;
                    padding: 0; font-size: 13px; font-weight: normal;
                    selection-background-color: #2563EB; selection-color: #FFFFFF; }}
                QDateEdit QLineEdit:disabled {{ color: {disabled}; }}
                QComboBox QAbstractItemView {{ background: {bg}; color: {fg};
                    selection-background-color: #2563EB; selection-color: #FFFFFF; }}
                QCalendarWidget QWidget {{ background: {bg}; color: {fg}; }}
                QCalendarWidget QAbstractItemView {{ background: {bg}; color: {fg};
                    selection-background-color: #2563EB; selection-color: #FFFFFF; }}
                QTableWidget {{ background: {bg}; color: {fg}; gridline-color: {border}; border: 1px solid {border}; }}
                QHeaderView::section {{ background: {bg}; color: {fg}; padding: 5px; border: none; border-bottom: 1px solid {border}; }}
                QPushButton {{ background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 5px; padding: 6px 16px; }}
                QPushButton:disabled {{ color: {disabled}; }}
                QPushButton#statsPeriodNav {{ padding: 0; font-size: 18px; font-weight: normal; }}
            """)
        title = I18n.tr('time_distribution')
        self.setWindowTitle(title)
        self.title_label.setText(title)
        self.total_label.setText(I18n.tr('stats_total').format(time=format_time(total)))
        warning = ('历史保存失败，正在重试；尚未保存的数据仍在内存。' if I18n.get_lang() in ('zh_CN','zh_TW') else 'History save failed; retrying. Unsaved data remains in memory.') if history_error else ''
        self.note_label.setText(warning)
        self.note_label.setVisible(bool(warning))
        self.close_button.setText(I18n.tr('stats_close'))
        self.table.setHorizontalHeaderLabels([I18n.tr('stats_timer'), I18n.tr('stats_duration'), I18n.tr('stats_share')])
        scroll = self.table.verticalScrollBar().value()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            name = row['name'] or I18n.tr('default_timer_name')
            name_item = QTableWidgetItem(name)
            name_item.setToolTip(name)
            swatch = QPixmap(12, 12)
            swatch.fill(QColor(COLORS[index % len(COLORS)]))
            name_item.setIcon(QIcon(swatch))
            self.table.setItem(index, 0, name_item)
            self.table.setItem(index, 1, QTableWidgetItem(format_time(row['seconds'])))
            self.table.setItem(index, 2, QTableWidgetItem(f"{row['share']:.1%}"))
        self.table.verticalScrollBar().setValue(scroll)
        self.chart.set_data(rows, total)

    def showEvent(self, event):
        self.refresh()
        self.refresh_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.refresh_timer.stop()
        super().hideEvent(event)


_dialog = None


def show_timer_statistics():
    global _dialog
    if _dialog is None:
        _dialog = TimerStatisticsDialog()
    _dialog.refresh()
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    return _dialog
