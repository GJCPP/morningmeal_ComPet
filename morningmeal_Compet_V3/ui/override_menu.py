"""Explicit app-scoped temporary assignment from either desktop overlay."""
from PyQt6.QtWidgets import QMenu
from core.i18n import I18n

_TEXT = {
 'zh_CN':('临时计入','默认 30 分钟','15 分钟','1 小时','直到取消','恢复自动','临时指定','请先切换到要指定的应用'),
 'zh_TW':('臨時計入','預設 30 分鐘','15 分鐘','1 小時','直到取消','恢復自動','臨時指定','請先切換到要指定的應用程式'),
 'en':('Temporarily count as','Default: 30 minutes','15 minutes','1 hour','Until cancelled','Automatic','Temporary','Switch to the target app first'),
 'ja':('一時的に計測先を指定','既定: 30分','15分','1時間','解除するまで','自動に戻す','一時指定','先に対象アプリへ切り替えてください'),
 'ko':('임시 타이머 지정','기본 30분','15분','1시간','취소할 때까지','자동 복원','임시 지정','먼저 대상 앱으로 전환하세요'),
}


def override_words():
    return dict(zip(('title','default','fifteen','hour','until','cancel','temporary','no_target'),
                    _TEXT.get(I18n.get_lang(),_TEXT['en'])))


def build_override_menu(parent=None, on_applied=None):
    from core.timer_fixes import controller
    from core.config_manager import config_mgr
    target = controller.override_target()  # Snapshot before the menu takes focus.
    words = override_words()
    menu = QMenu(words['title'] + (' · '+target[1] if target else ''),parent)
    if not target:
        menu.addAction(words['no_target']).setEnabled(False)
        return menu
    menu.addAction(words['default']).setEnabled(False)
    def add_choices(container,minutes):
        for timer in config_mgr.config.get('timers',[]):
            action = container.addAction(timer.get('name',''))
            action.setData((timer['id'],minutes))
            def apply(checked=False,ident=timer['id'],duration=minutes):
                controller.assign_override(target,ident,duration)
                if on_applied:
                    on_applied()
            action.triggered.connect(apply)
    add_choices(menu,30)
    menu.addSeparator()
    for label,minutes in ((words['fifteen'],15),(words['hour'],60),(words['until'],None)):
        add_choices(menu.addMenu(label),minutes)
    if controller.override_entry(target[0]):
        menu.addSeparator()
        def cancel():
            controller.cancel_override(target[0])
            if on_applied:
                on_applied()
        menu.addAction(words['cancel']).triggered.connect(cancel)
    return menu
