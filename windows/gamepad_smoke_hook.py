"""Verify the bundled SDL runtime with an isolated virtual device during builds."""
import os
if os.environ.get('COMPET_BUILD_SMOKE') == '1':
    import json
    from pathlib import Path
    import tempfile
    import time
    profile = Path(os.environ['USERPROFILE']).resolve(strict=True)
    if (profile.parent != Path(tempfile.gettempdir()).resolve()
            or not profile.name.startswith('compet-build-smoke-')):
        raise RuntimeError('Gamepad smoke requires an isolated build profile')
    from core.gamepad import SDLGamepads
    backend = SDLGamepads()
    sdl = backend.sdl
    ident = None
    try:
        index = sdl.SDL_JoystickAttachVirtual(sdl.SDL_JOYSTICK_TYPE_GAMECONTROLLER, 6, 15, 1)
        if index < 0:
            raise RuntimeError('Could not create build-test gamepad')
        ident = int(sdl.SDL_JoystickGetDeviceInstanceID(index))
        backend.poll(time.monotonic())
        joystick = backend.devices[ident][1]
        sdl.SDL_JoystickSetVirtualButton(joystick, 0, 1)
        state = backend.poll(time.monotonic()+0.1)[ident]
        if not state.buttons:
            raise RuntimeError('Bundled gamepad input verification failed')
        (profile/'gamepad-runtime.json').write_text(json.dumps({'runtime':True,'virtual_input':True}))
    finally:
        if ident in backend.devices:
            backend._close_device(ident)
        if ident is not None:
            for index in range(sdl.SDL_NumJoysticks()):
                if int(sdl.SDL_JoystickGetDeviceInstanceID(index)) == ident:
                    sdl.SDL_JoystickDetachVirtual(index)
                    break
        backend.close()
