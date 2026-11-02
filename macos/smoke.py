#!/usr/bin/env python3
"""Run the built bundle against a disposable profile, never the user's records."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app',type=Path)
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--duration',type=int,default=2500)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='compet-smoke-', dir='/private/tmp') as directory:
        profile = Path(directory)
        env = os.environ.copy()
        env.update(HOME=directory, COMPET_BUILD_SMOKE='1', COMPET_SMOKE_HOME=directory,
                   COMPET_SMOKE_DURATION_MS=str(args.duration))
        if args.native:
            env.pop('QT_QPA_PLATFORM',None)
        else:
            env['QT_QPA_PLATFORM']='offscreen'
        process = subprocess.run([str(args.app.resolve()/'Contents/MacOS/Compet-V3')],
            env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=args.duration/1000+30)
        crash = profile/'Library/Application Support/morningmeal_ComPet/crash_log.txt'
        if process.returncode or crash.exists() or not (profile/'result.json').exists():
            raise RuntimeError(f'Packaged smoke failed (exit={process.returncode}, result={(profile / "result.json").exists()}):\n'+(crash.read_text() if crash.exists() else '')+process.stdout)
        result = json.loads((profile/'result.json').read_text())
        assert result['pets'] == 1 and result['timers'] >= 1 and result['visible_timers'] == 1, result
        if args.native:
            assert len(result['native']) == 2 and result['quit_guard'], result
            assert all(not w['can_become_key'] for w in result['native']), result
            assert all(w['visible'] and w['active_space'] and w['behavior'] & 1 and w['behavior'] & (1<<8) and w['level'] >= 3 for w in result['native']), result
        assert (profile/'Library/Application Support/morningmeal_ComPet/skins/default/idle.png').exists()
        print('PASS: packaged '+('Cocoa' if args.native else 'offscreen')+' startup, resources and one-card display: '+json.dumps(result))

if __name__ == '__main__':
    main()
