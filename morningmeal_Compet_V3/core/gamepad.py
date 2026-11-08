"""Nonexclusive SDL gamepad polling; no input injection, rumble or event recording."""
from dataclasses import dataclass, field
import ctypes
import math
import sys
import time

from PyQt6.QtCore import QObject, QTimer


@dataclass
class PadState:
    buttons: frozenset = field(default_factory=frozenset)
    axes: dict = field(default_factory=dict)


class GamepadActivity:
    """Hysteresis rejects stick drift; held controls keep idle time fresh."""
    def __init__(self):
        self.previous = {}
        self.next_animation = 0.0

    def clear(self):
        self.previous.clear()
        self.next_animation = 0.0

    def sample(self, states, now):
        activity, payloads, current = False, [], {}
        for ident, state in states.items():
            old_buttons, old_axes = self.previous.get(ident, (frozenset(), frozenset()))
            axes = set()
            for prefix in ('left', 'right'):
                x, y = state.axes.get(prefix+'x', 0), state.axes.get(prefix+'y', 0)
                threshold = 0.15 if prefix+'_stick' in old_axes else 0.22
                if math.hypot(x, y) >= threshold:
                    axes.add(prefix+'_stick')
            for axis, value in state.axes.items():
                if axis in ('leftx', 'lefty', 'rightx', 'righty'):
                    continue
                threshold = (0.10 if axis in old_axes else 0.15) if axis.endswith('trigger') else (0.15 if axis in old_axes else 0.22)
                if abs(value) >= threshold:
                    axes.add(axis)
            axes = frozenset(axes)
            buttons = frozenset(state.buttons)
            activity |= bool(buttons or axes or old_buttons != buttons or old_axes != axes)
            payloads.extend('gamepad_'+button for button in sorted(buttons-old_buttons))
            if axes and (axes != old_axes or now >= self.next_animation):
                payloads.extend('gamepad_'+axis for axis in sorted(axes))
            current[ident] = (buttons, axes)
        self.previous = current  # Disconnected devices cannot remain active.
        if payloads:
            self.next_animation = now + 0.24
        return activity, '|'.join(dict.fromkeys(payloads))


class SDLGamepads:
    """Own only SDL's joystick subsystems; keep Qt in control of all GUI events."""
    def __init__(self):
        import sdl2
        self.sdl = sdl2
        self.devices = {}
        self.next_scan = 0.0
        self.flags = sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_GAMECONTROLLER
        sdl2.SDL_SetHint(sdl2.SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, b'1')
        if sdl2.SDL_InitSubSystem(self.flags) != 0:
            sdl2.SDL_QuitSubSystem(self.flags)
            raise RuntimeError('Gamepad initialization failed')
        sdl2.SDL_JoystickEventState(sdl2.SDL_DISABLE)
        sdl2.SDL_GameControllerEventState(sdl2.SDL_DISABLE)

    def _scan(self):
        s = self.sdl
        for ident, (controller, joystick, _) in list(self.devices.items()):
            if not s.SDL_JoystickGetAttached(joystick):
                self._close_device(ident)
        for index in range(max(0, s.SDL_NumJoysticks())):
            ident = int(s.SDL_JoystickGetDeviceInstanceID(index))
            if ident < 0 or ident in self.devices:
                continue
            controller = s.SDL_GameControllerOpen(index) if s.SDL_IsGameController(index) else None
            joystick = s.SDL_GameControllerGetJoystick(controller) if controller else s.SDL_JoystickOpen(index)
            if not joystick:
                if controller:
                    s.SDL_GameControllerClose(controller)
                continue
            # Unmapped USB axes can rest at an endpoint (for example a trigger).
            centers = {}
            if not controller:
                for axis in range(s.SDL_JoystickNumAxes(joystick)):
                    initial = ctypes.c_int16()
                    if s.SDL_JoystickGetAxisInitialState(joystick, axis, ctypes.byref(initial)):
                        centers[axis] = initial.value if abs(initial.value) > 29490 else 0
                    else:
                        centers[axis] = None
            self.devices[ident] = (controller, joystick, centers)

    def poll(self, now):
        s = self.sdl
        s.SDL_PumpEvents()
        s.SDL_JoystickUpdate()
        if now >= self.next_scan:
            self._scan()
            self.next_scan = now + 1.0
        states = {}
        for ident, (controller, joystick, centers) in list(self.devices.items()):
            if not s.SDL_JoystickGetAttached(joystick):
                self._close_device(ident)
                continue
            buttons, axes = set(), {}
            if controller:
                for button in range(s.SDL_CONTROLLER_BUTTON_MAX):
                    if s.SDL_GameControllerGetButton(controller, button):
                        name = s.SDL_GameControllerGetStringForButton(button)
                        buttons.add(name.decode('ascii') if name else 'button_'+str(button))
                for axis in range(s.SDL_CONTROLLER_AXIS_MAX):
                    name = s.SDL_GameControllerGetStringForAxis(axis)
                    if name:
                        value = s.SDL_GameControllerGetAxis(controller, axis) / 32767.0
                        axes[name.decode('ascii')] = max(-1.0, min(1.0, value))
            else:
                for button in range(s.SDL_JoystickNumButtons(joystick)):
                    if s.SDL_JoystickGetButton(joystick, button):
                        buttons.add('button_'+str(button))
                for axis in range(s.SDL_JoystickNumAxes(joystick)):
                    value = s.SDL_JoystickGetAxis(joystick, axis)
                    center = centers.get(axis)
                    if center is None:
                        initial = ctypes.c_int16()
                        if not s.SDL_JoystickGetAxisInitialState(joystick, axis, ctypes.byref(initial)):
                            continue
                        center = initial.value if abs(initial.value) > 29490 else 0
                        centers[axis] = center
                    axes['axis_'+str(axis)] = (value-center) / (65535.0 if center else 32767.0)
                for hat in range(s.SDL_JoystickNumHats(joystick)):
                    value = s.SDL_JoystickGetHat(joystick, hat)
                    for flag, direction in ((1,'up'),(2,'right'),(4,'down'),(8,'left')):
                        if value & flag:
                            buttons.add('dpad_'+direction)
            states[ident] = PadState(frozenset(buttons), axes)
        return states

    def _close_device(self, ident):
        controller, joystick, _ = self.devices.pop(ident)
        if controller:
            self.sdl.SDL_GameControllerClose(controller)
        else:
            self.sdl.SDL_JoystickClose(joystick)

    def close(self):
        for ident in list(self.devices):
            self._close_device(ident)
        self.sdl.SDL_QuitSubSystem(self.flags)


class GamepadMonitor(QObject):
    def __init__(self, app, backend_factory=SDLGamepads):
        super().__init__(app)
        self.backend_factory = backend_factory
        self.backend = None
        self.activity = GamepadActivity()
        self.next_retry = 0.0
        self.connected = 0
        self.unavailable = False
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.poll)
        self.timer.start()
        app.aboutToQuit.connect(self.stop)

    def poll(self):
        from core.config_manager import config_mgr
        from core import input_engine
        enabled = config_mgr.config.get('settings', {}).get('gamepad_enabled', True)
        if not enabled:
            self._close()
            input_engine.clear_gamepad_activity()
            return
        now = time.monotonic()
        try:
            if self.backend is None:
                if now < self.next_retry:
                    return
                self.backend = self.backend_factory()
            states = self.backend.poll(now)
            self.connected = len(states)
            self.unavailable = False
            if sys.platform == 'darwin':
                from core.timer_fixes import controller
                if not controller.allowed():
                    self.activity.clear()
                    input_engine.clear_gamepad_activity()
                    return
            active, payload = self.activity.sample(states, now)
            if active:
                input_engine.mark_gamepad_activity()
            if payload:
                input_engine.input_bridge.input_occurred.emit(payload, False)
        except Exception:
            # A missing driver/runtime or hot-unplug must not stop keyboard/timer operation.
            self._close()
            self.unavailable = True
            self.next_retry = now + 5.0

    def _close(self):
        if self.backend is not None:
            try:
                self.backend.close()
            except Exception:
                pass
            finally:
                self.backend = None
        self.connected = 0
        self.activity.clear()

    def stop(self):
        self.timer.stop()
        self._close()


def start(app):
    import os
    if (os.environ.get('COMPET_BUILD_SMOKE') == '1'
            or os.environ.get('QT_QPA_PLATFORM', '').lower() in ('offscreen', 'minimal')):
        return None
    if not hasattr(app, '_compet_gamepad_monitor'):
        app._compet_gamepad_monitor = GamepadMonitor(app)
    return app._compet_gamepad_monitor
