#!/usr/bin/env python3
"""Launch the current fixed-path installation once on each GUI login."""
import os
from pathlib import Path
import plistlib
import subprocess

APP = Path('/Applications/Compet-V3.app')
LABEL = 'com.gjcpp.compet.login'

def main():
    if not (APP/'Contents/MacOS/Compet-V3').is_file():
        raise SystemExit('Install the verified build at /Applications/Compet-V3.app first.')
    subprocess.run(['codesign','--verify','--deep','--strict',str(APP)],check=True)
    path = Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
    config = {'Label':LABEL, 'ProgramArguments':['/usr/bin/open','-g',str(APP)],
              'RunAtLoad':True, 'LimitLoadToSessionType':'Aqua'}
    if path.exists() and plistlib.loads(path.read_bytes()) != config:
        raise SystemExit(f'Existing startup entry differs; inspect it before replacing: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(plistlib.dumps(config))
    path.chmod(0o644)
    subprocess.run(['plutil','-lint',str(path)],check=True)
    domain = f'gui/{os.getuid()}'
    loaded = subprocess.run(['launchctl','print',f'{domain}/{LABEL}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0
    subprocess.run(['launchctl','enable',f'{domain}/{LABEL}'],check=True)
    if not loaded:
        subprocess.run(['launchctl','bootstrap',domain,str(path)],check=True)
    subprocess.run(['launchctl','print',f'{domain}/{LABEL}'],check=True)
    print(f'Login startup points to the current installed bundle: {APP}')

if __name__ == '__main__':
    main()
