"""Keep Cmd-Q local to its owning app; retain explicit quit and OS termination."""
from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtGui import QKeySequence
import AppKit


def is_native_quit_key(event):
    modifiers = int(event.modifierFlags())
    command = int(AppKit.NSEventModifierFlagCommand)
    extras = int(AppKit.NSEventModifierFlagShift | AppKit.NSEventModifierFlagControl
                 | AppKit.NSEventModifierFlagOption)
    return (bool(modifiers & command) and not modifiers & extras
            and str(event.charactersIgnoringModifiers() or '').casefold() == 'q')


def clear_quit_equivalents(menu):
    if menu is None:
        return
    command = int(AppKit.NSEventModifierFlagCommand)
    extras = int(AppKit.NSEventModifierFlagShift | AppKit.NSEventModifierFlagControl
                 | AppKit.NSEventModifierFlagOption)
    for item in menu.itemArray():
        mask = int(item.keyEquivalentModifierMask())
        if (str(item.keyEquivalent()).casefold() == 'q'
                and mask & command and not mask & extras):
            item.setKeyEquivalent_('')
        clear_quit_equivalents(item.submenu())


class QuitShortcutGuard(QObject):
    def __init__(self, app):
        super().__init__(app)
        self._app = app
        app.installEventFilter(self)
        # App-local monitor: does not observe or suppress any other app's events.
        self._callback = self.native_event
        self._monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            AppKit.NSEventMaskKeyDown, self._callback)
        if self._monitor is None:
            raise RuntimeError('Could not install the app-local quit shortcut guard')
        self._menu_timer = QTimer(self)
        self._menu_timer.timeout.connect(self.clear_native_shortcut)
        self._menu_timer.start(500)
        self.clear_native_shortcut()
        app.aboutToQuit.connect(self.cleanup)

    def native_event(self, event):
        return None if is_native_quit_key(event) else event

    def eventFilter(self, watched, event):
        if (event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
                and event.matches(QKeySequence.StandardKey.Quit)):
            event.accept()
            return True
        return False

    def clear_native_shortcut(self):
        clear_quit_equivalents(AppKit.NSApplication.sharedApplication().mainMenu())

    def cleanup(self):
        self._app.removeEventFilter(self)
        self._menu_timer.stop()
        if self._monitor is not None:
            AppKit.NSEvent.removeMonitor_(self._monitor)
            self._monitor = None


def install(app):
    if not hasattr(app, '_compet_quit_shortcut_guard'):
        app._compet_quit_shortcut_guard = QuitShortcutGuard(app)
    return app._compet_quit_shortcut_guard
