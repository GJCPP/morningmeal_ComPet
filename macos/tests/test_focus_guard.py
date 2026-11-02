"""Exercise the native/Qt quit guards without posting input to other apps."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin', 'macOS-specific shortcut protection')
class FocusGuardTests(unittest.TestCase):
    def test_local_shortcuts_and_explicit_quit(self):
        code = textwrap.dedent('''
            import AppKit
            from PyQt6.QtWidgets import QApplication, QWidget
            from PyQt6.QtCore import QEvent, QTimer, Qt
            from PyQt6.QtGui import QKeyEvent, QKeySequence
            from core.macos_focus import install, is_native_quit_key, clear_quit_equivalents
            app = QApplication([])
            app.setQuitOnLastWindowClosed(False)
            guard = install(app)
            assert guard is install(app)
            class Event:
                def __init__(self, text, flags): self.text, self.flags = text, flags
                def charactersIgnoringModifiers(self): return self.text
                def modifierFlags(self): return self.flags
            cmd = int(AppKit.NSEventModifierFlagCommand)
            shift = int(AppKit.NSEventModifierFlagShift)
            control = int(AppKit.NSEventModifierFlagControl)
            event = Event('q',cmd)
            assert is_native_quit_key(event) and guard.native_event(event) is None
            for event in (Event('q',0), Event('q',control), Event('q',cmd|shift), Event('c',cmd)):
                assert not is_native_quit_key(event)
                assert guard.native_event(event) is event
            menu = AppKit.NSMenu.alloc().initWithTitle_('Test')
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_('Quit','terminate:','q')
            item.setKeyEquivalentModifierMask_(cmd)
            menu.addItem_(item)
            clear_quit_equivalents(menu)
            assert item.keyEquivalent() == ''
            assert str(item.action()) == 'terminate:'
            key = QKeySequence(QKeySequence.StandardKey.Quit)[0]
            for kind in (QEvent.Type.ShortcutOverride,QEvent.Type.KeyPress):
                event = QKeyEvent(kind,key.key(),key.keyboardModifiers())
                assert guard.eventFilter(app,event) and event.isAccepted()
            assert not guard.eventFilter(app,QEvent(QEvent.Type.Quit))
            assert not guard.eventFilter(app,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_C,Qt.KeyboardModifier.ControlModifier))
            exited=[]
            app.aboutToQuit.connect(lambda:exited.append(True))
            QTimer.singleShot(10,app.quit)
            assert app.exec() == 0
            assert exited == [True] and guard._monitor is None
            print('PASS: local Cmd-Q blocked, other keys unchanged, menu action retained, explicit quit works')
        ''')
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT/'morningmeal_Compet_V3')
        env['QT_QPA_PLATFORM'] = 'cocoa'
        result = subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
