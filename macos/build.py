#!/usr/bin/env python3
"""Build, sign, verify and install the current source at the fixed application path."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'macos/artifacts'
APP = OUT / 'dist/Compet-V3.app'

def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-only',action='store_true',help='Validate staging without publishing it.')
    options = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'morningmeal_Compet_V3'
    from PIL import Image
    icon = OUT / 'app_icon.icns'
    Image.open(source / 'assets/app_icon.png').save(icon)
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
            '--name', 'Compet-V3', '--osx-bundle-identifier', 'Compet-V3',
            '--distpath', OUT/'dist', '--workpath', OUT/'work', '--specpath', OUT,
            '--icon', icon, '--add-data', f'{source / "assets"}:assets',
            '--runtime-hook', ROOT/'macos/smoke_hook.py', '--collect-submodules', 'pynput']
    for name in ['AppKit', 'Quartz', 'HIServices', 'core.docking', 'core.timer_policy',
                 'core.timer_fixes', 'core.macos_foreground', 'core.interaction_fixes',
                 'core.macos_compat']:
        args += ['--hidden-import', name]
    run(*args, source/'main.py', cwd=source)
    info_path = APP / 'Contents/Info.plist'
    info = plistlib.loads(info_path.read_bytes())
    info['LSUIElement'] = True
    info_path.write_bytes(plistlib.dumps(info))
    paths = sorted(source.rglob('*.py'))
    manifest = {'format': 2, 'kind': 'source-build',
        'revision': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'python': sys.version.split()[0],
        'sources': {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'assets': {str(p.relative_to(source/'assets')):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted((source/'assets').rglob('*')) if p.is_file()}}
    (APP/'Contents/Resources/compet-build.json').write_text(json.dumps(manifest, indent=2)+'\n')
    run(sys.executable, ROOT/'macos/sign_app.py', '--app', APP)
    run(sys.executable, ROOT/'macos/smoke.py', APP)
    run(sys.executable, ROOT/'macos/smoke.py', APP, '--native')
    print(f'Prepared and verified: {APP}')
    if not options.build_only:
        run(sys.executable, ROOT/'macos/install.py')

if __name__ == '__main__':
    main()
