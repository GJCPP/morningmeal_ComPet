"""Require explicit settings entry after closing/minimizing an accessory window."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from PyQt6.QtCore import QObject, QEvent, Qt


class SettingsVisibilityGuard(QObject):
    def __init__(self, window, diagnostic_path=None):
        super().__init__(window)
        self.window = window
        self.requested = False
        self.events = []
        self.path = Path(diagnostic_path) if diagnostic_path else None
        window.installEventFilter(self)
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self.detach)

    def record(self, event, source=None):
        item = {'time':datetime.now(timezone.utc).isoformat(timespec='seconds'),'event':event}
        if source:
            item['source'] = source if source in ('tray-menu','pet-menu','timer-menu') else 'other-explicit'
        self.events = (self.events + [item])[-100:]
        if self.path is not None:
            temporary = self.path.with_suffix('.tmp')
            try:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                with open(temporary,'w',encoding='utf-8') as stream:
                    os.chmod(temporary,0o600)
                    json.dump(self.events,stream,ensure_ascii=False)
                os.replace(temporary,self.path)
            except OSError:
                pass  # Diagnostics must not interfere with normal UI operation.

    def open(self, source):
        self.record('explicit-open',source)
        self.requested = True
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind in (QEvent.Type.Show,QEvent.Type.WindowActivate) and not self.requested:
            self.record('blocked-show' if kind==QEvent.Type.Show else 'blocked-activation')
            self.window.hide()
            return True
        if kind == QEvent.Type.Hide:
            self.requested = False
            self.record('hidden')
        elif kind == QEvent.Type.WindowStateChange and self.window.windowState() & Qt.WindowState.WindowMinimized:
            self.record('minimized-hidden')
            self.window.hide()
        return False

    def detach(self):
        self.window.removeEventFilter(self)
