# Local ComPet macOS maintenance

- Preserve upstream history. Work on `codex/` branches, inspect Git status first, and commit only task files. Push only when the user explicitly requests it.
- `macos/README.md` explains the installed compatibility snapshot and the distinction between the repaired release app and a future source rebuild.
- Do not modify or re-sign `/Applications/Compet-V3.app` just to synchronize this repository. Application installation is a separate task and requires GUI checks plus permission-refresh instructions.
- Input monitoring remains listen-only and user-authorized. Never edit TCC databases or bypass missing permissions.
- Do not commit applications, archives, user settings, skins copied from Application Support, timer records, logs, tokens, or credentials.
- Validate source syntax with `python3 -m compileall -q morningmeal_Compet_V3 macos`; use `python3 macos/check_installed.py` to compare the local installed hook and signature, run `python3 -m unittest discover -s macos/tests -p 'test_*.py' -v` for docking regressions, and run `git diff --check`.
- Fullscreen/window/permission behavior requires real macOS GUI verification. An offscreen smoke test does not prove those behaviors.

- Local production updates must use `macos/sign_app.py` with the existing dedicated identity receipt. Do not replace it with ad-hoc signing or regenerate the key. Identity creation and code-signing trust changes require explicit user approval; private keys never enter Git or CI.

- Current timing behavior is implemented by `core/timer_fixes.py` and `core/timer_policy.py`, replacing the legacy ActivityEngine start path. Keep foreground selection independent of idle state, never reuse an unknown foreground, and do not display multiple native timer windows in current/recent mode. Preserve cumulative history and canonical multi-timer pet associations.
