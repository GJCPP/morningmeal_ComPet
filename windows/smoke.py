"""Check the packaged Windows app with an isolated temporary user profile."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    executable = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='compet-build-smoke-') as profile:
        env = os.environ.copy()
        env.update(USERPROFILE=profile, QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1', COMPET_BUILD_SMOKE='1')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        with open(Path(profile) / 'stderr.txt', 'w+b') as errors:
            process = subprocess.Popen(
                [str(executable)], cwd=executable.parent, env=env,
                stdout=subprocess.DEVNULL, stderr=errors, startupinfo=startup,
            )
            try:
                try:
                    code = process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    code = None
                errors.flush()
                errors.seek(0)
                log = errors.read().decode('utf-8', errors='replace')
                data = Path(profile) / '.morningmeal_ComPet'
                crash = data / 'crash_log.txt'
                if crash.exists():
                    raise RuntimeError(crash.read_text(encoding='utf-8'))
                if code is not None or 'Traceback' in log:
                    raise RuntimeError(f'App failed startup (exit={code}): {log}')
                if not (data / 'skins/羿/idle.png').is_file():
                    raise RuntimeError(f'Default resources were not initialized: {log}')
                if not (Path(profile) / 'gamepad-runtime.json').is_file():
                    raise RuntimeError(f'Bundled SDL runtime was not verified: {log}')
                print('Packaged startup, default resources and virtual gamepad input: passed')
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
