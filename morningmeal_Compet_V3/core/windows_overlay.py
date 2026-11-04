"""Recover a Windows tool overlay whose native z-order no longer matches its flags."""
import ctypes
from ctypes import wintypes
import sys

from PyQt6.QtCore import QObject, QTimer


class NativeWindowOrder:
    def __init__(self):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetWindow.restype = wintypes.HWND
        self.user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.get_style = (self.user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8
                          else self.user32.GetWindowLongW)
        self.get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        self.get_style.restype = ctypes.c_ssize_t
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.dwm = ctypes.WinDLL('dwmapi')
        self.dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

    def needs_raise(self, handle, foreground=None):
        foreground = foreground or self.user32.GetForegroundWindow()
        if not foreground or foreground == handle:
            return False
        own_pid, foreground_pid = wintypes.DWORD(), wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(handle, ctypes.byref(own_pid))
        self.user32.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))
        # Keep settings, menus and intentionally topmost applications accessible.
        if own_pid.value == foreground_pid.value:
            return False
        if self.get_style(foreground, -20) & 0x8:  # WS_EX_TOPMOST
            return False
        cloaked = wintypes.DWORD()
        if (self.dwm.DwmGetWindowAttribute(handle, 14, ctypes.byref(cloaked), 4) == 0
                and cloaked.value):
            return False
        # Inspect the actual order: WS_EX_TOPMOST may survive a shell/desktop
        # transition even when the overlay has fallen behind an ordinary window.
        current = self.user32.GetWindow(handle, 3)  # GW_HWNDPREV
        for _ in range(512):
            if not current:
                return False
            if current == foreground:
                return True
            current = self.user32.GetWindow(current, 3)
        return False

    def restore_topmost(self, handle):
        # QWidget.raise_() alone cannot repair a lost native topmost flag.
        return bool(self.user32.SetWindowPos(handle, wintypes.HWND(-1), 0, 0, 0, 0,
            0x2 | 0x1 | 0x10 | 0x200))  # NOMOVE | NOSIZE | NOACTIVATE | NOOWNERZORDER


class OverlayRecovery(QObject):
    def __init__(self, app, native=None):
        super().__init__(app)
        self.app = app
        self.native = native or NativeWindowOrder()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.recover)
        self.timer.start()
        QTimer.singleShot(0, self.recover)

    def recover(self):
        from ui.pet_widget import PetWidget
        for pet in self.app.topLevelWidgets():
            if (isinstance(pet, PetWidget) and pet.isVisible() and not pet.isMinimized()
                    and self.native.needs_raise(int(pet.winId()))):
                self.native.restore_topmost(int(pet.winId()))


def install(app):
    if sys.platform != 'win32':
        return None
    if not hasattr(app, '_compet_overlay_recovery'):
        app._compet_overlay_recovery = OverlayRecovery(app)
    return app._compet_overlay_recovery
