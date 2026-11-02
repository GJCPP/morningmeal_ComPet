#!/usr/bin/env python3
"""Publish a verified source build at the fixed login-startup path."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'macos/artifacts/dist/Compet-V3.app'
TARGET = Path('/Applications/Compet-V3.app')
STAGED = Path('/Applications/.Compet-V3.installing.app')
PREVIOUS = Path('/Applications/.Compet-V3.previous.app')

def run(*args):
    subprocess.run([str(a) for a in args],check=True)

def main():
    if subprocess.run(['pgrep','-x','Compet-V3'],stdout=subprocess.DEVNULL).returncode == 0:
        raise SystemExit('ComPet is running. Fully exit through its menu to save records before installation.')
    run(sys.executable,ROOT/'macos/check_installed.py','--app',SOURCE)
    if STAGED.exists() or PREVIOUS.exists():
        raise SystemExit('Previous install staging exists; inspect it before continuing.')
    run('/usr/bin/ditto',SOURCE,STAGED)
    run(sys.executable,ROOT/'macos/check_installed.py','--app',STAGED)
    had_previous = TARGET.exists()
    if had_previous:
        TARGET.rename(PREVIOUS)
    try:
        STAGED.rename(TARGET)
        run(sys.executable,ROOT/'macos/check_installed.py','--app',TARGET)
    except BaseException:
        if TARGET.exists():
            TARGET.rename(STAGED)
        if had_previous:
            PREVIOUS.rename(TARGET)
        raise
    if PREVIOUS.exists():
        shutil.rmtree(PREVIOUS)
    print(f'Installed current source build: {TARGET}')

if __name__ == '__main__':
    main()
