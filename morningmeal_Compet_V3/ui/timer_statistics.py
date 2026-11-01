"""Live, read-only pie chart of every timer, without extra chart dependencies."""
import math
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from core.config_manager import config_mgr
from core.i18n import I18n
from core.timer_statistics import timer_distribution
from ui.components import format_time


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

    def refresh(self):
        rows, total = timer_distribution(config_mgr.config.get('timers', []))
        dark = config_mgr.config.get('settings', {}).get('dark_mode', False)
        snapshot = (tuple((row['id'], row['name'], row['seconds']) for row in rows), I18n.get_lang(), dark)
        if snapshot == self._last_snapshot:
            return
        self._last_snapshot = snapshot
        if self._dark != dark:
            self._dark = dark
            bg, fg, border = ('#18181B', '#FAFAFA', '#3F3F46') if dark else ('#FFFFFF', '#111827', '#D1D5DB')
            self.setStyleSheet(f"""
                QDialog#timerStatisticsDialog {{ background: {bg}; }}
                QLabel {{ color: {fg}; }}
                QTableWidget {{ background: {bg}; color: {fg}; gridline-color: {border}; border: 1px solid {border}; }}
                QHeaderView::section {{ background: {bg}; color: {fg}; padding: 5px; border: none; border-bottom: 1px solid {border}; }}
                QPushButton {{ background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 5px; padding: 6px 16px; }}
            """)
        title = I18n.tr('time_distribution')
        self.setWindowTitle(title)
        self.title_label.setText(title)
        self.total_label.setText(I18n.tr('stats_total').format(time=format_time(total)))
        self.note_label.setText(I18n.tr('stats_note'))
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
