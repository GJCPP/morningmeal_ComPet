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

## Windows local builds

- Use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File windows/build.ps1` for local Windows updates. See `windows/README.md`.
- Keep the fixed desktop `ComPet.lnk` and `morningmeal_Compet_V3/dist/Compet-V3/Compet-V3.exe` path. Do not create new version-suffixed executables/directories or ZIP archives for ordinary local rebuilds.
- Let the script stage, smoke-test, and publish the build. Never force-stop a user's running app to replace it; ask them to exit through the tray menu if the fixed app is running.
- Run the Qt editing regression with `.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v` when changing timer settings.

## Tracking and interaction rules

- Window groups have expandable tracking rows; never truncate saved groups to three entries.
- All matching ordinary timers accrue independently, with their own pause/idle checks. Only the first matching timer in configuration/list order is displayed.
- A timer with `is_fallback: true` covers only foreground tasks unmatched by every ordinary timer. Paused or idle ordinary matches must not be redirected into it. Missing/failed foreground reads and the app's own UI do not accrue fallback time.
- A fallback timer's existence enables global pet keyboard/mouse response, even if paused. Its name is editable and does not determine its role. This must not bypass input-monitoring permissions or alter timer accounting.
