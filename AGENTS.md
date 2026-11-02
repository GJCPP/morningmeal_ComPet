# Local ComPet macOS maintenance

- Preserve upstream history. Work and commit directly on local `main`, tracking the fork’s `origin/main`; do not create task branches or worktrees unless the user explicitly requests one. Inspect Git status and remote differences first, preserve uncommitted user work, and commit only task files. Push only when the user explicitly requests it; never force-push or silently overwrite conflicts.
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

## Shared local build policy

- Reuse this checkout’s existing `.venv` and installed build toolchain for ordinary updates. Do not create a separate environment, checkout, or renamed build for each task. Change dependencies only when required, and update the existing environment and lockfile deliberately.
- Rebuild into the same fixed output paths and replace the existing compiled artifacts after validation. Do not accumulate version/date/task-suffixed applications, executables, build directories, desktop shortcuts, or ZIP archives.
- On macOS, reuse `macos/artifacts/dist/Compet-V3.app` and publish to `/Applications/Compet-V3.app`; keep the existing signing identity and login-startup path. On Windows, reuse the fixed paths documented below. Temporary test profiles/staging may be used for safe verification, then cleaned up; they must not become alternate installations.
- Preserve user settings, skins, timer history, and layout. If the app is running, obtain a normal menu quit to save records before replacement; never force-stop it to rebuild. Do not rebuild or reinstall for documentation-only or Git-only work.

## macOS source builds

- Use `.venv/bin/python macos/build.py` for full local rebuilds; it validates and installs at `/Applications/Compet-V3.app`. Use `--build-only` for isolated staging.
- Preserve the fixed install path and `com.gjcpp.compet.login` LaunchAgent. Login startup must open that path through LaunchServices, without `-n` or KeepAlive. Never point startup at a temporary or versioned build.
- `macos/install.py` refuses replacement while ComPet is running. Ask for a menu quit only when needed; never force-stop the real app to install.
- Smoke tests use disposable profiles, disable input listeners/permission requests, and never copy live settings. Source-build identity and file hashes are checked via `macos/check_installed.py`.

## Numeric settings and bundled default

- Use `ui.numeric_editor.SettingsSpinBox` for settings integer fields. Preserve editor focus/card identity during value changes and external refreshes; do not reintroduce styled NoButtons/nested padding.
- The user explicitly selected “羿” as the bundled default. Only those requested default assets are versioned; unrelated user skins remain private. Preserve customized skins and timer records during migration.
- Run `tests/test_numeric_editors.py` for numeric changes, including `COMPET_QT_TEST_PLATFORM=cocoa` on macOS; use isolated profiles. Source-build asset manifests must match the packaged resources.
