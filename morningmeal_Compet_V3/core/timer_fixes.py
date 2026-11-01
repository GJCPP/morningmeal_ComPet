"""One current/recent timer, accurate foreground accounting, and shared pet docks."""
import os
import time
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMenu
from core.config_manager import config_mgr, SKINS_DIR
from core.i18n import I18n
from core.timer_policy import TimerSession, associated_ids, migrate_preferences
from core.docking import docking_score, timer_position_below_pet
from core import activity_engine as activity_module, input_engine, window_tracker
from ui.pet_widget import PetWidget
from ui.timer_widget import TimerWidget
from ui.settings.tab_pet import PetCardWidget
from ui import components

_INSTALLED = False
_TEXT = {
    'zh_CN': ('计时中','闲置 · 暂停','最近使用 · 未匹配','已手动暂停','前台识别暂不可用','需要输入监控权限','跟随当前计时器（全部）','已关联 {count} 个（右键调整）','关联计时器','解除全部关联'),
    'zh_TW': ('計時中','閒置 · 暫停','最近使用 · 未匹配','已手動暫停','前台辨識暫不可用','需要輸入監控權限','跟隨目前計時器（全部）','已關聯 {count} 個（右鍵調整）','關聯計時器','解除全部關聯'),
    'en': ('Counting','Idle · paused','Recent · no match','Paused','App detection unavailable','Input permission needed','Follow current timer (all)','{count} linked (right-click to edit)','Linked timers','Unlink all'),
    'ja': ('計測中','アイドル · 停止','最近使用 · 未一致','一時停止中','アプリを取得できません','入力監視の許可が必要','現在のタイマーに追従（すべて）','{count}個を連携（右クリックで編集）','連携タイマー','すべて解除'),
    'ko': ('측정 중','유휴 · 일시정지','최근 사용 · 일치 없음','일시정지','앱 감지 불가','입력 모니터링 권한 필요','현재 타이머 따라가기 (전체)','{count}개 연결 (우클릭 편집)','연결 타이머','전체 연결 해제'),
}
_REASONS = ['counting','idle','unmatched','paused','unavailable','permission']


def text(index):
    return _TEXT.get(I18n.get_lang(), _TEXT['en'])[index]


def widgets(kind):
    return [widget for widget in QApplication.topLevelWidgets() if isinstance(widget, kind)] if QApplication.instance() else []


class CurrentTimerController:
    def __init__(self):
        self.session = TimerSession(config_mgr.config.get('settings', {}).get('recent_timer_id'))
        self.foreground = window_tracker.get_active_window_info
        self.idle = lambda: max(0, time.time() - input_engine.get_last_activity_time())
        self.allowed = lambda: True
        self.clock = time.monotonic
        self.engine = activity_module.activity_engine
        self.dirty = False
        self.last_save = self.clock()
        self._refreshing = False

    def display_id(self):
        ids = [timer['id'] for timer in config_mgr.config.get('timers', [])]
        if self.session.display_id not in ids:
            recent = config_mgr.config.get('settings', {}).get('recent_timer_id')
            self.session.display_id = recent if recent in ids else (ids[0] if ids else None)
        return self.session.display_id

    def should_show(self, timer):
        return timer.timer_data.get('id') == self.display_id()

    def step(self):
        now = self.clock()
        previous = (self.session.display_id, self.session.reason, self.session.matched_id)
        try:
            info = self.foreground()
            available = bool(info)
            own_window = bool(info and info.pid == os.getpid())
            names = () if own_window else getattr(info, 'aliases', (info.app_name,))
            title = '' if own_window else info.title
            idle, allowed = self.idle(), bool(self.allowed())
        except Exception:
            info, names, title, idle, allowed, available = window_tracker.WindowInfo(), (), '', float('inf'), False, False
        # Always replace the foreground snapshot, including failures and our own settings.
        self.engine.current_app_name = names[0] if names else ''
        self.engine.current_window_title = title
        self.engine.current_window_id = info.window_id if available else None
        updated = self.session.step(config_mgr.config, names, title, idle, now, allowed=allowed, available=available)
        self.engine.last_input_time = time.time() - max(0, idle)
        if self.session.matched_id:
            config_mgr.config.setdefault('settings', {})['recent_timer_id'] = self.session.matched_id
        changed = previous != (self.session.display_id, self.session.reason, self.session.matched_id)
        self.dirty |= bool(updated) or changed
        if updated:
            self.engine.tick.emit(updated)
        if changed:
            self.engine.active_window_changed.emit(self.engine.current_app_name)
        self.refresh_widgets()
        if self.dirty and (changed or now - self.last_save >= 5):
            config_mgr.save_config()
            self.last_save, self.dirty = now, False

    def refresh_widgets(self):
        if self._refreshing:
            return
        self._refreshing = True
        try:
            display = self.display_id()
            timers = {widget.timer_data['id']:widget for widget in widgets(TimerWidget)}
            for timer_id, widget in timers.items():
                if timer_id == display:
                    if not widget.isVisible():
                        _ORIGINAL_SHOW(widget)
                    if hasattr(widget, 'label_status'):
                        widget.label_status.setText(text(_REASONS.index(self.session.reason)))
                else:
                    widget.hide()
            for pet in widgets(PetWidget):
                ids = associated_ids(pet.pet_data, config_mgr.config.get('timers', []))
                pet.pet_data['bound_timer_id'] = display if display in ids else ''
                # All linked cards share one anchor; only one card is presented.
                for timer_id in ids:
                    timer = timers.get(timer_id)
                    if timer is None:
                        continue
                    drag = getattr(timer, '_compet_drag_filter', None)
                    if drag is not None and drag.offset is not None:
                        continue
                    x, y = timer_position_below_pet((pet.x(),pet.y(),pet.width(),pet.height()),(timer.width(),timer.height()))
                    timer.move(x,y)
                    timer.timer_data.update(x=x,y=y)
        finally:
            self._refreshing = False

    def is_active(self, timer_id):
        timer = next((item for item in config_mgr.config.get('timers', []) if item['id']==timer_id),None)
        if timer is None:
            return True
        try:
            return (timer_id in self.session.matched_ids and not timer.get('paused',False)
                    and self.allowed() and self.idle() <= timer.get('idle_timeout',5))
        except Exception:
            return False

    def stop(self):
        self.engine.running = False
        timer = getattr(self.engine,'_current_timer_poll',None)
        if timer:
            timer.stop()
        config_mgr.save_config()


controller = CurrentTimerController()
_ORIGINAL_SHOW = TimerWidget.show


def _set_links(pet_data, ids, follow=False):
    timers = config_mgr.config.get('timers', [])
    valid = [timer['id'] for timer in timers]
    ids = valid[:] if follow else list(dict.fromkeys(item for item in ids if item in valid))
    for other in config_mgr.config.get('pets', []):
        if other.get('id') == pet_data.get('id'):
            continue
        remaining = [item for item in associated_ids(other,timers) if item not in ids]
        if remaining != associated_ids(other,timers):
            other['follow_current_timer'] = False
            other['bound_timer_ids'] = remaining
            if other.get('bound_timer_id') not in remaining:
                other['bound_timer_id'] = ''
    pet_data['bound_timer_ids'] = ids
    pet_data['follow_current_timer'] = follow
    pet_data['bound_timer_id'] = controller.display_id() if controller.display_id() in ids else ''
    controller.refresh_widgets()
    config_mgr.save_config()


def _toggle_link(pet, timer_id, checked):
    ids = associated_ids(pet.pet_data,config_mgr.config.get('timers',[]))
    _set_links(pet.pet_data,ids+[timer_id] if checked else [item for item in ids if item!=timer_id])
    pet.dock_changed.emit()


def install(foreground=None, idle=None, allowed=None):
    global _INSTALLED
    if foreground:
        controller.foreground = foreground
        window_tracker.get_active_window_info = foreground
        activity_module.get_active_window_info = foreground
        def picker_info():
            info = foreground()
            if info and not info.title:
                return window_tracker.WindowInfo(title=info.app_name, app_name=info.app_name, window_id=info.window_id, pid=info.pid)
            return info
        components.get_active_window_info = picker_info
    if idle:
        controller.idle = idle
    if allowed:
        controller.allowed = allowed
    if _INSTALLED:
        return
    if migrate_preferences(config_mgr.config):
        config_mgr.save_config()
    controller.session.display_id = config_mgr.config['settings'].get('recent_timer_id')
    def start(self):
        if self.running:
            return
        self.running = True
        controller.engine = self
        self.m_listener = self.k_listener = self.worker_thread = None
        self._current_timer_poll = QTimer(self)
        self._current_timer_poll.timeout.connect(lambda: controller.step() if self.running else None)
        self._current_timer_poll.start(200)
        app = QApplication.instance()
        if not getattr(app,'_compet_timer_shutdown_hook',False):
            app.aboutToQuit.connect(controller.stop)
            app._compet_timer_shutdown_hook = True
        controller.step()
    activity_module.ActivityEngine.start = start
    activity_module.ActivityEngine.is_timer_active = lambda self,timer_id: controller.is_active(timer_id)
    activity_module.ActivityEngine._evaluate_timers = lambda self,now: controller.step()

    original_timer_init = TimerWidget.__init__
    def timer_init(self,*args,**kwargs):
        original_timer_init(self,*args,**kwargs)
        self.label_status = QLabel(text(2))
        self.label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_status.setStyleSheet('background:transparent;color:#64748B;font-size:10px;')
        self.layout().addWidget(self.label_status)
        self.label_status.installEventFilter(self._compet_drag_filter)
    TimerWidget.__init__ = timer_init
    def show(self):
        if controller.should_show(self):
            _ORIGINAL_SHOW(self)
        else:
            self.hide()
    TimerWidget.show = show

    def bind(self,timer_id):
        follow = self.pet_data.get('follow_current_timer',False)
        ids = associated_ids(self.pet_data,config_mgr.config.get('timers',[]))
        _set_links(self.pet_data,ids+[timer_id],follow=follow)
        self.dock_changed.emit()
    def unbind(self):
        _set_links(self.pet_data,[])
        self.dock_changed.emit()
    PetWidget.bind_to_timer,PetWidget.unbind_timer = bind,unbind
    PetWidget.initial_dock_check = lambda self: controller.refresh_widgets()

    def pet_release(self,event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.accept()
            return
        display = controller.display_id()
        linked = associated_ids(self.pet_data,config_mgr.config.get('timers',[]))
        if display not in linked and config_mgr.config.get('settings',{}).get('magnetic_snap',True):
            candidates=[]
            for timer in self.get_all_timers_callback():
                if not timer.isVisible():
                    continue
                score=docking_score((self.x(),self.y(),self.width(),self.height()),(timer.x(),timer.y(),timer.width(),timer.height()),config_mgr.config.get('settings',{}).get('snap_distance',15))
                if score is not None:
                    candidates.append((score,timer))
            if candidates:
                self.bind_to_timer(min(candidates,key=lambda item:item[0])[1].timer_data['id'])
        self.pet_data.update(x=self.x(),y=self.y())
        controller.refresh_widgets()
        config_mgr.save_config()
        event.accept()
    PetWidget.mouseReleaseEvent = pet_release

    # Adding another timer to an already-linked pet must not be rejected.
    from core import interaction_fixes
    def pet_for_timer(timer,position):
        if not config_mgr.config.get('settings',{}).get('magnetic_snap',True):
            return None
        if timer.get_bound_pet_callback(timer.timer_data['id']) is not None:
            return None
        candidates=[]
        for pet in widgets(PetWidget):
            if not pet.isVisible():
                continue
            score=docking_score((pet.x(),pet.y(),pet.width(),pet.height()),(position.x(),position.y(),timer.width(),timer.height()),config_mgr.config.get('settings',{}).get('snap_distance',15))
            if score is not None:
                candidates.append((score,pet))
        return min(candidates,key=lambda item:item[0])[1] if candidates else None
    interaction_fixes._pet_for_timer = pet_for_timer

    def refresh_timers(self):
        combo=self.bound_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(I18n.tr('unbound'),'')
        combo.addItem(text(6),'__all__')
        ids=associated_ids(self.pet_data,config_mgr.config.get('timers',[]))
        selected='__all__' if self.pet_data.get('follow_current_timer') else ids[0] if len(ids)==1 else '__multiple__' if ids else ''
        if len(ids)>1 and not self.pet_data.get('follow_current_timer'):
            combo.addItem(text(7).format(count=len(ids)),'__multiple__')
        for timer in config_mgr.config.get('timers',[]):
            combo.addItem(timer.get('name',''),timer['id'])
        combo.setCurrentIndex(max(0,combo.findData(selected)))
        combo.blockSignals(False)
    PetCardWidget.refresh_timers = refresh_timers
    def on_bound_changed(self,index):
        choice=self.bound_combo.itemData(index)
        if choice=='__multiple__':
            return
        _set_links(self.pet_data,[] if not choice else [choice],follow=choice=='__all__')
        self.changed.emit()
    PetCardWidget.on_bound_timer_changed = on_bound_changed

    def context(self,event):
        menu=QMenu(self)
        settings=menu.addAction(I18n.tr('open_settings'))
        duplicate=menu.addAction(I18n.tr('duplicate_pet'))
        remove=menu.addAction(I18n.tr('remove_pet'))
        submenu=menu.addMenu(text(8))
        follow=submenu.addAction(text(6));follow.setCheckable(True);follow.setChecked(self.pet_data.get('follow_current_timer',False))
        def all_changed(checked):
            _set_links(self.pet_data,[],follow=checked)
            self.dock_changed.emit()
        follow.triggered.connect(all_changed)
        ids=associated_ids(self.pet_data,config_mgr.config.get('timers',[]))
        for timer in config_mgr.config.get('timers',[]):
            action=submenu.addAction(timer.get('name',''));action.setCheckable(True);action.setChecked(timer['id'] in ids)
            action.triggered.connect(lambda checked,tid=timer['id']:_toggle_link(self,tid,checked))
        submenu.addSeparator();submenu.addAction(text(9)).triggered.connect(self.unbind_timer)
        skin_menu=menu.addMenu(I18n.tr('change_skin'))
        if os.path.isdir(SKINS_DIR):
            for skin in sorted(os.listdir(SKINS_DIR)):
                if os.path.isdir(os.path.join(SKINS_DIR,skin)):
                    action=skin_menu.addAction(skin);action.setCheckable(True);action.setChecked(skin==self.pet_data.get('skin'))
                    action.triggered.connect(lambda checked,name=skin:self.change_skin_direct(name))
        exit_action=menu.addAction(I18n.tr('tray_exit'))
        chosen=menu.exec(event.globalPos())
        if chosen==settings:
            self.open_settings_callback()
        elif chosen==duplicate and self.duplicate_callback:
            source=dict(self.pet_data,bound_timer_id='',bound_timer_ids=[],follow_current_timer=False)
            self.duplicate_callback(source)
        elif chosen==remove and self.remove_callback:
            self.remove_callback(self.pet_data['id'])
        elif chosen==exit_action:
            QApplication.quit()
    PetWidget.contextMenuEvent = context
    I18n.language_changed.connect(controller.refresh_widgets)
    _INSTALLED = True
