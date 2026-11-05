"""Gamepad deadzones, held-input activity, disconnects and timer integration."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'morningmeal_Compet_V3'))
from core.gamepad import GamepadActivity, PadState


class GamepadActivityTests(unittest.TestCase):
    def test_rest_connection_and_center_drift_are_not_activity(self):
        activity = GamepadActivity()
        state = PadState(axes={'leftx':0.04,'lefty':-0.03,'rightx':0.06,'lefttrigger':0.02})
        self.assertEqual(activity.sample({1:state},0),(False,''))
        self.assertEqual(activity.sample({1:state},5),(False,''))
        self.assertEqual(activity.sample({},6),(False,''))

    def test_button_edges_and_long_holds_keep_activity_without_event_flood(self):
        activity = GamepadActivity()
        state = PadState(frozenset(('a',)))
        self.assertEqual(activity.sample({1:state},0),(True,'gamepad_a'))
        self.assertEqual(activity.sample({1:state},60),(True,''))
        self.assertEqual(activity.sample({1:PadState()},61),(True,''))
        self.assertEqual(activity.sample({1:PadState()},62),(False,''))
        self.assertEqual(activity.sample({1:state},63),(True,'gamepad_a'))

    def test_stick_hysteresis_and_bounded_animation_rate(self):
        activity = GamepadActivity()
        self.assertEqual(activity.sample({1:PadState(axes={'leftx':0.3})},0),(True,'gamepad_left_stick'))
        self.assertEqual(activity.sample({1:PadState(axes={'leftx':0.18})},0.1),(True,''))
        self.assertEqual(activity.sample({1:PadState(axes={'leftx':0.18})},0.3),(True,'gamepad_left_stick'))
        self.assertEqual(activity.sample({1:PadState(axes={'leftx':0.1})},0.4),(True,''))
        self.assertEqual(activity.sample({1:PadState(axes={'leftx':0.1})},1),(False,''))

    def test_triggers_generic_axes_multiple_pads_and_disconnect(self):
        activity = GamepadActivity()
        active,payload = activity.sample({1:PadState(axes={'lefttrigger':0.5}),
            2:PadState(frozenset(('dpad_up',)),{'axis_0':0.7})},0)
        self.assertTrue(active)
        self.assertEqual(set(payload.split('|')),{'gamepad_lefttrigger','gamepad_dpad_up','gamepad_axis_0'})
        self.assertEqual(activity.sample({},100),(False,''))
        self.assertEqual(activity.sample({2:PadState()},101),(False,''))


class GamepadQtTests(unittest.TestCase):
    def test_monitor_timer_permissions_settings_and_silent_pet_interaction(self):
        probe = textwrap.dedent("""
            import os, types
            from unittest.mock import patch
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtTest import QSignalSpy
            app = QApplication([])
            with patch('os.path.expanduser',return_value=os.environ['COMPET_TEST_PROFILE']):
                from core.config_manager import config_mgr
            from core import input_engine
            from core.gamepad import GamepadMonitor, PadState, start
            from core.interaction_fixes import install
            install()
            from core.timer_fixes import install as install_timers, controller
            install_timers()
            from core.timer_policy import TimerSession
            from core.window_tracker import WindowInfo
            from ui.pet_widget import PetWidget
            from ui.settings.main_window import MainSettingWindow
            from core.i18n import I18n
            from main import MorningmealComPetApp, sound_mgr
            config_mgr.config['groups'] = {'game':['Game']}
            config_mgr.config['timers'] = [dict(id='game',name='Game',group='game',
                idle_timeout=5,elapsed_seconds=0)]
            config_mgr.config['pets'][0].update(bound_timer_id='game',bound_timer_ids=['game'])
            controller.session = TimerSession()
            controller.foreground = lambda: WindowInfo(app_name='Game',window_id=123,pid=os.getpid()+100)
            controller.idle = lambda: 120  # Simulate native macOS idle ignoring gamepads.
            controller.allowed = lambda: True
            controller.clock = lambda: 0
            controller.step()
            assert controller.session.reason == 'idle'
            class Backend:
                def __init__(self):
                    self.states = {}
                    self.closed = False
                def poll(self,now): return self.states
                def close(self): self.closed = True
            made = []
            def factory():
                backend = Backend(); made.append(backend); return backend
            monitor = GamepadMonitor(app, factory)
            monitor.timer.stop()
            app._compet_gamepad_monitor = monitor
            spy = QSignalSpy(input_engine.input_bridge.input_occurred)
            pet = PetWidget(dict(config_mgr.config['pets'][0]),lambda:[],lambda:None,None,None)
            runner = types.SimpleNamespace(pet_widgets=[pet])
            input_engine.input_bridge.input_occurred.connect(
                lambda payload,mouse: MorningmealComPetApp.on_input_event(runner,payload,mouse))
            monitor.poll()
            assert made and not spy
            made[-1].states = {1:PadState(frozenset(('a',)))}
            with patch('core.gamepad.sys.platform','darwin'), patch.object(controller,'allowed',return_value=False):
                monitor.poll()
                assert not spy and input_engine.get_gamepad_idle_time() == float('inf')
            with patch.object(sound_mgr,'play_key') as key, patch.object(sound_mgr,'play_click') as click:
                monitor.poll()
                assert len(spy) == 1 and spy[0][0] == 'gamepad_a'
                assert not key.called and not click.called
            assert len(pet.hit_times) == 1
            assert input_engine.get_gamepad_idle_time() < 1
            controller.clock = lambda: 1
            controller.step()
            controller.clock = lambda: 2
            controller.step()
            assert config_mgr.config['timers'][0]['elapsed_seconds'] == 1
            # Held controls refresh idle without continuously emitting button presses.
            monitor.poll()
            assert len(spy) == 1
            config_mgr.config['timers'][0]['paused'] = True
            controller.clock = lambda: 3
            controller.step()
            assert controller.session.reason == 'paused'
            config_mgr.config['timers'][0]['paused'] = False
            controller.allowed = lambda: False
            controller.clock = lambda: 4
            controller.step()
            assert controller.session.reason == 'permission'
            assert not controller.is_active('game')
            controller.allowed = lambda: True
            made[-1].states = {}
            monitor.poll()
            assert monitor.connected == 0 and len(spy) == 1
            window = MainSettingWindow()
            window.tab_pet.refresh_gamepad_status()
            for lang in ('zh_CN','en','ja','ko','zh_TW'):
                I18n.set_language(lang)
                assert window.tab_pet.gamepad_cb.text() == I18n.tr('gamepad_enabled')
            # Turning off stops reads, clears gamepad idle, and persists.
            previous_backend = made[-1]
            window.tab_pet.gamepad_cb.setChecked(False)
            monitor.poll()
            assert previous_backend.closed and monitor.backend is None
            assert input_engine.get_gamepad_idle_time() == float('inf')
            assert not config_mgr.load_config()['settings']['gamepad_enabled']
            window.tab_pet.gamepad_cb.setChecked(True)
            monitor.poll()
            assert len(made) == 2
            # SDL failure and even a failing cleanup cannot abort the rest of the app.
            def fail(now): raise OSError('test unplug')
            def close_fail(): raise OSError('test close')
            made[-1].poll = fail
            made[-1].close = close_fail
            monitor.poll()
            assert monitor.unavailable and monitor.backend is None
            monitor.poll()
            assert len(made) == 2, 'Failed backend retried every poll'
            monitor.stop()
            assert start(app) is None, 'Offscreen tests must not monitor physical devices'
            window.close(); pet.close()
        """)
        with tempfile.TemporaryDirectory(prefix='compet-gamepad-test-') as profile:
            env = os.environ.copy()
            env.update(USERPROFILE=profile,COMPET_TEST_PROFILE=profile,QT_QPA_PLATFORM='offscreen',
                PYTHONUTF8='1',PYTHONPATH=str(ROOT/'morningmeal_Compet_V3'))
            result = subprocess.run([sys.executable,'-X','utf8','-c',probe],cwd=ROOT,env=env,
                capture_output=True,text=True,encoding='utf-8',timeout=25)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_sdl_virtual_controller_input_and_hotplug(self):
        from core.gamepad import SDLGamepads
        import time
        backend = SDLGamepads()
        sdl, ident = backend.sdl, None
        try:
            index = sdl.SDL_JoystickAttachVirtual(sdl.SDL_JOYSTICK_TYPE_GAMECONTROLLER,6,15,1)
            self.assertGreaterEqual(index,0)
            ident = int(sdl.SDL_JoystickGetDeviceInstanceID(index))
            now = time.monotonic()
            backend.poll(now)
            joystick = backend.devices[ident][1]
            sdl.SDL_JoystickSetVirtualButton(joystick,0,1)
            state = backend.poll(now+0.1)[ident]
            self.assertIn('a',state.buttons)
            sdl.SDL_JoystickSetVirtualButton(joystick,0,0)
            sdl.SDL_JoystickSetVirtualAxis(joystick,0,22000)
            state = backend.poll(now+0.2)[ident]
            self.assertFalse(state.buttons)
            self.assertGreater(state.axes['leftx'],0.6)
            # Detach the test device only; never manipulate a physical controller.
            sdl.SDL_JoystickDetachVirtual(index)
            self.assertNotIn(ident,backend.poll(now+2))
        finally:
            if ident in backend.devices: backend._close_device(ident)
            if ident is not None:
                for index in range(sdl.SDL_NumJoysticks()):
                    if int(sdl.SDL_JoystickGetDeviceInstanceID(index)) == ident:
                        sdl.SDL_JoystickDetachVirtual(index)
                        break
            backend.close()
