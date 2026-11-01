#!/usr/bin/env python3
"""Sign a prepared ComPet bundle with a pinned, persistent certificate identity."""
import argparse
import json
from pathlib import Path
import plistlib
import re
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True,help='Prepared output bundle; validate it before installing.')
    parser.add_argument('--identity',help='40-digit certificate SHA-1; defaults to the dedicated local identity receipt.')
    args=parser.parse_args()
    if args.identity is None:
        receipt = Path.home()/'.config/compet-signing/identity.json'
        try:
            args.identity = json.loads(receipt.read_text())['sha1']
        except (OSError, ValueError, KeyError):
            parser.error('No dedicated identity receipt; supply --identity or explicitly create the local identity first.')
    if not isinstance(args.identity, str) or not re.fullmatch(r'[0-9a-fA-F]{40}',args.identity):
        parser.error('A full certificate fingerprint is required; ad-hoc and identifier-only signing are not accepted.')
    app=args.app.resolve(strict=True)
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier')!='Compet-V3':
        parser.error('This tool only signs the Compet-V3 bundle identifier.')
    identity=args.identity.upper()
    requirement=f'identifier "Compet-V3" and certificate leaf = H"{identity}"'
    subprocess.run(['codesign','--force','--sign',identity,'--timestamp=none',
                    '--requirements','=designated => '+requirement,str(app)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    subprocess.run(['codesign','--verify','--test-requirement','='+requirement,str(app)],check=True)
    print('Signed and verified with a stable certificate-pinned requirement.')


if __name__=='__main__':
    main()
