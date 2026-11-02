"""Packaged smoke harness; inert unless an isolated build-test profile is supplied."""
import os
if os.environ.get('COMPET_BUILD_SMOKE') == '1':
    import json
    from pathlib import Path
    profile = Path(os.environ['COMPET_SMOKE_HOME']).resolve(strict=True)
    if profile.parent != Path('/private/tmp') or not profile.name.startswith('compet-smoke-'):
        raise RuntimeError('Smoke test requires a dedicated temporary profile')
    os.environ['HOME'] = str(profile)
    from core.config_manager import config_mgr
    # Keep a visible pet in the isolated default profile; no user records are copied.
    config_mgr.config['pets'] = [{'id':'smoke-pet','skin':'羿','x':300,'y':300,'scale':1}]
    if os.environ.get('QT_QPA_PLATFORM', '').lower() not in ('offscreen', 'minimal'):
        import core.macos_compat as compat
        compat._compet_listen_allowed = lambda: False
        compat._compet_request_listen = lambda: False
        compat._compet_permission_requested = True
    from core import input_engine
    input_engine.start_input_engine = lambda: None
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    _exec = QApplication.exec
    def smoke_exec(self):
        def finish():
            from ui.pet_widget import PetWidget
            from ui.timer_widget import TimerWidget
            widgets = self.topLevelWidgets()
            pets = [w for w in widgets if isinstance(w, PetWidget)]
            timers = [w for w in widgets if isinstance(w, TimerWidget)]
            result = {'pets':len(pets),'timers':len(timers),'visible_timers':sum(w.isVisible() for w in timers)}
            if os.environ.get('QT_QPA_PLATFORM', '').lower() not in ('offscreen','minimal'):
                import objc
                import AppKit
                result['activation_policy'] = int(AppKit.NSApplication.sharedApplication().activationPolicy())
                result['native'] = []
                for w in pets + [w for w in timers if w.isVisible()]:
                    window = objc.objc_object(c_void_p=int(w.winId())).window()
                    result['native'].append({'behavior':int(window.collectionBehavior()),'level':int(window.level()),'visible':bool(window.isVisible()),'active_space':bool(window.isOnActiveSpace()),'can_become_key':bool(window.canBecomeKeyWindow())})
                result['quit_guard'] = hasattr(self, '_compet_quit_shortcut_guard')
            (profile/'result.json').write_text(json.dumps(result))
            self.quit()
        QTimer.singleShot(int(os.environ.get('COMPET_SMOKE_DURATION_MS','2500')),finish)
        return _exec()
    QApplication.exec = smoke_exec
