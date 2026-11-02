#!/usr/bin/env python3
"""Read-only check that a repaired ComPet bundle matches this branch's patch."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'morningmeal_Compet_V3/core/macos_compat.py'

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path('/Applications/Compet-V3.app'))
    args = parser.parse_args()
    baseline = json.loads((ROOT / 'macos/installed-baseline.json').read_text())
    manifest_path = args.app / 'Contents/Resources/compet-build.json'
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        sources = manifest.get('sources', {})
        expected = {str(p.relative_to(ROOT)) for p in (ROOT / 'morningmeal_Compet_V3').rglob('*.py')}
        if manifest.get('kind') != 'source-build' or set(sources) != expected:
            parser.error('Source-build manifest is incomplete.')
        for name, digest in sources.items():
            if sha256(ROOT / name) != digest:
                parser.error(f'Installed build differs from source: {name}')
        if manifest.get('format', 1) >= 2:
            asset_root = ROOT / 'morningmeal_Compet_V3/assets'
            assets = manifest.get('assets', {})
            expected_assets = {str(p.relative_to(asset_root)) for p in asset_root.rglob('*') if p.is_file()}
            installed_root = args.app / 'Contents/Resources/assets'
            installed_assets = {str(p.relative_to(installed_root)) for p in installed_root.rglob('*') if p.is_file()}
            if set(assets) != expected_assets or installed_assets != expected_assets:
                parser.error('Source-build asset manifest is incomplete or contains obsolete resources.')
            for name, digest in assets.items():
                if sha256(asset_root / name) != digest or sha256(installed_root / name) != digest:
                    parser.error(f'Installed asset differs from source: {name}')
        print(f'Source build matches repository files (base {manifest["revision"][:7]}).')
    else:
        hook = args.app / 'Contents/Resources/compet_macos_compat.py'
        original_main = args.app / 'Contents/Resources/compet_original_main.marshal'
        if not hook.is_file() or not original_main.is_file():
            parser.error('Expected a locally repaired bundle containing its hook and saved original main.')
        if sha256(SOURCE) != sha256(hook):
            parser.error('Installed compatibility hook differs from repository source.')
        for source_name, bundle_name in [('docking.py', 'compet_docking.py'), ('interaction_fixes.py', 'compet_interaction_fixes.py'), ('timer_policy.py', 'compet_timer_policy.py'), ('timer_fixes.py', 'compet_timer_fixes.py'), ('macos_foreground.py', 'compet_macos_foreground.py')]:
            source = ROOT / 'morningmeal_Compet_V3/core' / source_name
            installed = args.app / 'Contents/Resources' / bundle_name
            if not installed.is_file() or sha256(source) != sha256(installed):
                parser.error(f'Installed {bundle_name} differs from repository source.')
        if sha256(original_main) != baseline['original_main_sha256']:
            parser.error('Saved original main differs from the captured installed baseline.')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(args.app)], check=True)
    identity = baseline.get('signing_certificate_sha1')
    if identity:
        requirement = f'=identifier "Compet-V3" and certificate leaf = H"{identity}"'
        subprocess.run(['codesign', '--verify', '--test-requirement', requirement, str(args.app)], check=True)
    print('PASS: installed code matches repository source; fixed signature is valid.')

if __name__ == '__main__':
    main()
