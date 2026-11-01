"""Local macOS 15 compatibility patch: capture the keyboard layout on the main thread.
Pynput's listener already keeps one layout context for its lifetime; only the
thread used to obtain that context changes. No permissions are granted here.
"""
import contextlib as _compet_contextlib
import pynput.keyboard._darwin as _compet_keyboard
with _compet_keyboard.keycode_context() as _compet_layout:
    pass
@_compet_contextlib.contextmanager
def _compet_keycode_context():
    yield _compet_layout
_compet_keyboard.keycode_context = _compet_keycode_context
import Quartz as _compet_Quartz
_compet_quartz_status = {}
for _compet_fn in ['CGEventGetLocation','CGEventGetFlags','CGEventGetIntegerValueField','CGEventKeyboardGetUnicodeString','CGEventTapCreate','CGEventTapEnable','CFRunLoopGetCurrent','CGEventTapIsEnabled','kCGEventMouseMoved','kCGEventScrollWheel','kCGScrollWheelEventDeltaAxis2','kCGScrollWheelEventDeltaAxis1']:
    try:
        _compet_quartz_status[_compet_fn] = str(type(getattr(_compet_Quartz,_compet_fn)))
    except Exception as _compet_exc:
        _compet_quartz_status[_compet_fn] = repr(_compet_exc)
import HIServices as _compet_hiservices
_compet_hiservices.AXIsProcessTrusted

# Keep pet overlays visible across Spaces and other applications' full-screen spaces.
import objc as _compet_objc
import AppKit as _compet_AppKit
from PyQt6.QtCore import QTimer as _compet_QTimer, Qt as _compet_Qt
import ui.pet_widget as _compet_pet_module
_compet_original_flags = _compet_pet_module.PetWidget.update_window_flags
_compet_window_status = {}
def _compet_apply_window(widget):
    try:
        view = _compet_objc.objc_object(c_void_p=int(widget.winId()))
        window = view.window()
        if window is None:
            return
        behavior = int(window.collectionBehavior())
        behavior &= ~((1 << 1) | (1 << 7) | (1 << 9) | (1 << 16) | (1 << 17))
        behavior |= (1 << 0) | (1 << 8) | (1 << 18)
        window.setCollectionBehavior_(behavior)
        window.setStyleMask_(int(window.styleMask()) | (1 << 7))
        window.setHidesOnDeactivate_(False)
        window.setLevel_(max(int(window.level()), int(_compet_AppKit.NSFloatingWindowLevel)))
        _compet_window_status.update(behavior=int(window.collectionBehavior()),level=int(window.level()), active_space=bool(window.isOnActiveSpace()), panel=bool(window.isKindOfClass_(_compet_AppKit.NSPanel)))
    except Exception as exc:
        _compet_window_status['error'] = repr(exc)
def _compet_update_flags(self):
    flags = _compet_Qt.WindowType.FramelessWindowHint | _compet_Qt.WindowType.WindowStaysOnTopHint | _compet_Qt.WindowType.Tool
    if _compet_pet_module.config_mgr.config.get('settings', {}).get('click_through', False):
        flags |= _compet_Qt.WindowType.WindowTransparentForInput
    self.setWindowFlags(flags)
    self.show()
    _compet_QTimer.singleShot(0, lambda: _compet_apply_window(self))
_compet_pet_module.PetWidget.update_window_flags = _compet_update_flags

# macOS native event observer using existing Accessibility authorization.
# The callback always returns the original event; no input is suppressed or stored.
import ctypes as _compet_ct
import threading as _compet_threads
import core.input_engine as _compet_engine
_compet_cg = _compet_ct.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_compet_cf = _compet_ct.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
_compet_callback_type = _compet_ct.CFUNCTYPE(_compet_ct.c_void_p, _compet_ct.c_void_p, _compet_ct.c_uint32, _compet_ct.c_void_p, _compet_ct.c_void_p)
def _compet_bind(lib, name, result, args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, args
    return fn
_compet_ptr = _compet_ct.c_void_p
_compet_u32 = _compet_ct.c_uint32
_compet_u64 = _compet_ct.c_uint64
_compet_make_tap = _compet_bind(_compet_cg,'CGEventTapCreate',_compet_ptr,[_compet_u32,_compet_u32,_compet_u32,_compet_u64,_compet_callback_type,_compet_ptr])
_compet_enable_tap = _compet_bind(_compet_cg,'CGEventTapEnable',None,[_compet_ptr,_compet_ct.c_bool])
_compet_tap_enabled = _compet_bind(_compet_cg,'CGEventTapIsEnabled',_compet_ct.c_bool,[_compet_ptr])
_compet_event_integer = _compet_bind(_compet_cg,'CGEventGetIntegerValueField',_compet_ct.c_int64,[_compet_ptr,_compet_u32])
_compet_event_flags = _compet_bind(_compet_cg,'CGEventGetFlags',_compet_u64,[_compet_ptr])
_compet_event_unicode = _compet_bind(_compet_cg,'CGEventKeyboardGetUnicodeString',None,[_compet_ptr,_compet_u64,_compet_ct.POINTER(_compet_u64),_compet_ct.POINTER(_compet_ct.c_uint16)])
_compet_make_source = _compet_bind(_compet_cf,'CFMachPortCreateRunLoopSource',_compet_ptr,[_compet_ptr,_compet_ptr,_compet_ct.c_long])
_compet_current_loop = _compet_bind(_compet_cf,'CFRunLoopGetCurrent',_compet_ptr,[])
_compet_add_source = _compet_bind(_compet_cf,'CFRunLoopAddSource',None,[_compet_ptr,_compet_ptr,_compet_ptr])
_compet_run_loop = _compet_bind(_compet_cf,'CFRunLoopRun',None,[])
_compet_default_mode = _compet_ptr.in_dll(_compet_cf,'kCFRunLoopDefaultMode').value
_compet_listen_allowed = _compet_bind(_compet_cg,'CGPreflightListenEventAccess',_compet_ct.c_bool,[])
_compet_ax = _compet_ct.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
_compet_ax_trusted = _compet_bind(_compet_ax,'AXIsProcessTrusted',_compet_ct.c_bool,[])
_compet_native_state = {'created':False, 'error':None}
_compet_native_tap = None
_compet_special_keys = {key.value.vk:key for key in _compet_engine.keyboard.Key if key.value.vk is not None}
_compet_modifier_masks = {54:1<<20,55:1<<20,56:1<<17,60:1<<17,58:1<<19,61:1<<19,59:1<<18,62:1<<18,57:1<<16}
def _compet_translate_key(event):
    vk = int(_compet_event_integer(event, 9))
    if vk in _compet_special_keys:
        return _compet_special_keys[vk]
    length = _compet_u64()
    buf = (_compet_ct.c_uint16 * 8)()
    _compet_event_unicode(event, 8, _compet_ct.byref(length), buf)
    text = _compet_ct.string_at(buf, min(length.value,8)*2).decode('utf-16-le',errors='replace')
    if text:
        return _compet_engine.keyboard.KeyCode.from_char(text[0])
    return _compet_engine.keyboard.KeyCode.from_vk(vk)
@_compet_callback_type
def _compet_native_callback(proxy, event_type, event, refcon):
    try:
        if event_type in (0xFFFFFFFE, 0xFFFFFFFF) and _compet_listen_allowed():
            _compet_enable_tap(_compet_native_tap, True)
        elif event_type in (10,11):
            key = _compet_translate_key(event)
            (_compet_engine.on_key_press if event_type == 10 else _compet_engine.on_key_release)(key)
        elif event_type == 12:
            vk = int(_compet_event_integer(event,9))
            key = _compet_special_keys.get(vk)
            mask = _compet_modifier_masks.get(vk)
            if key is not None and mask is not None:
                (_compet_engine.on_key_press if _compet_event_flags(event)&mask else _compet_engine.on_key_release)(key)
        elif event_type in (1,2,3,4,25,26):
            number = int(_compet_event_integer(event,3))
            button = {0:_compet_engine.mouse.Button.left,1:_compet_engine.mouse.Button.right,2:_compet_engine.mouse.Button.middle}.get(number)
            if button is not None:
                _compet_engine.on_mouse_click(0,0,button,event_type in (1,3,25))
        elif event_type in (5,6,7,27,22):
            _compet_engine._mark_activity()
    except Exception as exc:
        _compet_native_state['error'] = type(exc).__name__ + ': ' + str(exc)
    return event
def _compet_native_worker():
    global _compet_native_tap
    mask = sum(1<<n for n in (1,2,3,4,5,6,7,10,11,12,22,25,26,27))
    _compet_native_tap = _compet_make_tap(1,0,1,mask,_compet_native_callback,None)
    _compet_native_state['created'] = bool(_compet_native_tap)
    if not _compet_native_tap:
        _compet_native_state['error'] = 'macOS denied the listen-only event tap'
        return
    source = _compet_make_source(None,_compet_native_tap,0)
    _compet_add_source(_compet_current_loop(),source,_compet_default_mode)
    _compet_enable_tap(_compet_native_tap, True)
    _compet_run_loop()
def _compet_ensure_native_input():
    if not _compet_listen_allowed():
        return
    thread = getattr(_compet_engine, '_compet_native_thread', None)
    if thread is None or not thread.is_alive():
        thread = _compet_threads.Thread(target=_compet_native_worker,name='ComPet-native-input',daemon=True)
        _compet_engine._compet_native_thread = thread
        thread.start()
    elif _compet_native_tap and not _compet_tap_enabled(_compet_native_tap):
        _compet_enable_tap(_compet_native_tap, True)
def _compet_start_native_input():
    _compet_ensure_native_input()
    if not hasattr(_compet_engine, '_compet_permission_timer'):
        from PyQt6.QtWidgets import QApplication
        timer = _compet_QTimer(QApplication.instance())
        timer.timeout.connect(_compet_ensure_native_input)
        timer.start(2000)
        _compet_engine._compet_permission_timer = timer
_compet_engine.start_input_engine = _compet_start_native_input

# Clear transparent pixels every frame; disable Cocoa's cached alpha-mask shadow.
from PyQt6.QtGui import QPainter as _compet_Painter
from PyQt6.QtWidgets import QApplication as _compet_GuiApplication
_compet_paint_original = _compet_pet_module.PetWidget.paintEvent
def _compet_clear_and_paint(self, event):
    painter = _compet_Painter(self)
    painter.setCompositionMode(_compet_Painter.CompositionMode.CompositionMode_Source)
    painter.fillRect(self.rect(), _compet_Qt.GlobalColor.transparent)
    painter.end()
    _compet_paint_original(self, event)
_compet_pet_module.PetWidget.paintEvent = _compet_clear_and_paint

# Accessory apps' nonactivating floating panels can accompany other apps' full-screen spaces.
_compet_gui_init_original = _compet_GuiApplication.__init__
def _compet_gui_init(self, *args, **kwargs):
    _compet_gui_init_original(self, *args, **kwargs)
    _compet_AppKit.NSApplication.sharedApplication().setActivationPolicy_(1)
_compet_GuiApplication.__init__ = _compet_gui_init
_compet_apply_window_original = _compet_apply_window
def _compet_apply_window(widget):
    _compet_apply_window_original(widget)
    try:
        view = _compet_objc.objc_object(c_void_p=int(widget.winId()))
        window = view.window()
        if window is None:
            return
        window.setOpaque_(False)
        window.setBackgroundColor_(_compet_AppKit.NSColor.clearColor())
        window.setHasShadow_(False)
        window.setCanHide_(False)
        window.setHidesOnDeactivate_(False)
        window.setLevel_(int(_compet_AppKit.NSStatusWindowLevel))
        if window.isKindOfClass_(_compet_AppKit.NSPanel):
            window.setFloatingPanel_(True)
            window.setBecomesKeyOnlyIfNeeded_(True)
        window.orderFrontRegardless()
    except Exception as exc:
        _compet_window_status['display_error'] = repr(exc)

def _compet_refresh_overlays(notification):
    for widget in _compet_GuiApplication.topLevelWidgets():
        if isinstance(widget, _compet_pet_module.PetWidget) and widget.isVisible():
            _compet_apply_window(widget)

def _compet_watch_spaces():
    try:
        workspace = _compet_AppKit.NSWorkspace.sharedWorkspace()
        observer = workspace.notificationCenter().addObserverForName_object_queue_usingBlock_(
            _compet_AppKit.NSWorkspaceActiveSpaceDidChangeNotification, None,
            _compet_AppKit.NSOperationQueue.mainQueue(), _compet_refresh_overlays)
        _compet_GuiApplication.instance()._compet_space_observer = observer
    except Exception as exc:
        _compet_window_status['space_observer_error'] = repr(exc)
_compet_start_input_original = _compet_engine.start_input_engine
def _compet_start_input_with_space_watch():
    _compet_start_input_original()
    _compet_watch_spaces()
_compet_engine.start_input_engine = _compet_start_input_with_space_watch

# Apply the same nonactivating panel treatment to timer cards and newly shown timers.
import ui.timer_widget as _compet_timer_module
def _compet_timer_flags(self):
    flags = _compet_Qt.WindowType.FramelessWindowHint | _compet_Qt.WindowType.WindowStaysOnTopHint | _compet_Qt.WindowType.Tool
    self.setWindowFlags(flags)
    _compet_QTimer.singleShot(0, lambda: _compet_apply_window(self))
_compet_timer_module.TimerWidget.update_window_flags = _compet_timer_flags
_compet_timer_show_original = _compet_timer_module.TimerWidget.showEvent
def _compet_timer_show(self, event):
    _compet_timer_show_original(self, event)
    _compet_QTimer.singleShot(0, lambda: _compet_apply_window(self))
_compet_timer_module.TimerWidget.showEvent = _compet_timer_show

def _compet_refresh_overlays(notification):
    for widget in _compet_GuiApplication.topLevelWidgets():
        if isinstance(widget, (_compet_pet_module.PetWidget, _compet_timer_module.TimerWidget)) and widget.isVisible():
            _compet_apply_window(widget)
