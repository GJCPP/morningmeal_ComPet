"""Read the frontmost app without AppleScript, window IDs, or Screen Recording."""
import ctypes
import time
import AppKit
from core.window_tracker import WindowInfo

_cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_ax = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
_cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
_ptr = ctypes.c_void_p


def _bind(library, name, result, arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, arguments
    return function


_idle = _bind(_cg, 'CGEventSourceSecondsSinceLastEventType', ctypes.c_double, [ctypes.c_int32, ctypes.c_uint32])
_trusted = _bind(_ax, 'AXIsProcessTrusted', ctypes.c_bool, [])
_app_element = _bind(_ax, 'AXUIElementCreateApplication', _ptr, [ctypes.c_int32])
_copy_attr = _bind(_ax, 'AXUIElementCopyAttributeValue', ctypes.c_int32, [_ptr, _ptr, ctypes.POINTER(_ptr)])
_timeout = _bind(_ax, 'AXUIElementSetMessagingTimeout', ctypes.c_int32, [_ptr, ctypes.c_float])
_release = _bind(_cf, 'CFRelease', None, [_ptr])
_string = _bind(_cf, 'CFStringCreateWithCString', _ptr, [_ptr, ctypes.c_char_p, ctypes.c_uint32])
_length = _bind(_cf, 'CFStringGetLength', ctypes.c_long, [_ptr])
_cstring = _bind(_cf, 'CFStringGetCString', ctypes.c_bool, [_ptr, ctypes.c_void_p, ctypes.c_long, ctypes.c_uint32])
_type_id = _bind(_cf, 'CFGetTypeID', ctypes.c_ulong, [_ptr])
_string_type_id = _bind(_cf, 'CFStringGetTypeID', ctypes.c_ulong, [])
_utf8 = 0x08000100
_focused_window = _string(None, b'AXFocusedWindow', _utf8)
_window_title = _string(None, b'AXTitle', _utf8)
_cache = {}


def idle_seconds():
    return max(0.0, float(_idle(0, 0xFFFFFFFF)))


def app_aliases(name, bundle_id):
    names = [name, bundle_id]
    bundle_id = (bundle_id or '').casefold()
    if bundle_id.startswith('com.tencent.xinwechat'):
        names += ['微信', 'WeChat']
    elif bundle_id == 'com.tencent.qq' or bundle_id.startswith('com.tencent.qq.'):
        names += ['QQ']
    elif bundle_id == 'com.openai.codex':
        names += ['ChatGPT', 'Codex']
    return tuple(value for value in names if value)


def _title(pid):
    now = time.monotonic()
    cached = _cache.get(pid)
    if cached and now - cached[0] < 0.75:
        return cached[1]
    title = ''
    if _trusted():
        application = _app_element(pid)
        window, text = _ptr(), _ptr()
        try:
            _timeout(application, 0.05)
            if _copy_attr(application, _focused_window, ctypes.byref(window)) == 0 and window.value:
                _timeout(window, 0.05)
                if _copy_attr(window, _window_title, ctypes.byref(text)) == 0 and text.value and _type_id(text) == _string_type_id():
                    buffer = ctypes.create_string_buffer(_length(text) * 4 + 1)
                    if _cstring(text, buffer, len(buffer), _utf8):
                        title = buffer.value.decode('utf-8', errors='replace')
        finally:
            for value in (text, window):
                if value.value:
                    _release(value)
            if application:
                _release(application)
    _cache.clear()
    _cache[pid] = (now, title)
    return title


def get_active_window_info():
    try:
        front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if front is None:
            return WindowInfo()
        pid = int(front.processIdentifier())
        name = str(front.localizedName() or '')
        bundle = str(front.bundleIdentifier() or '')
        try:
            title = _title(pid)
        except Exception:
            title = ''  # App identity remains valid even if title access is unavailable.
        info = WindowInfo(title=title, app_name=name, window_id=pid, pid=pid)
        info.bundle_id = bundle
        info.aliases = app_aliases(name, bundle)
        return info
    except Exception:
        return WindowInfo()
