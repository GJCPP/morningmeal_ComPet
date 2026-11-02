"""Shared, keyboard-editable integer control for styled settings panels."""
from PyQt6.QtWidgets import QAbstractSpinBox, QSpinBox
from PyQt6.QtCore import Qt


class SettingsSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Qt 6 styled NoButtons can collapse the embedded editor. Keep native
        # steppers and remove the nested QLineEdit's second border/padding.
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.lineEdit().setStyleSheet(
            'border: none; border-radius: 0; padding: 0; background: transparent;')
        self.setMinimumHeight(max(28, self.fontMetrics().height() + 12))
        self.setMinimumWidth(84)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Commit a complete number on Enter/focus-out, rather than saving a
        # partial value (or clamping its first digit) during replacement typing.
        self.setKeyboardTracking(False)
