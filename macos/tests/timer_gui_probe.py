"""Qt integration regression; caller must intercept configuration/skin writes."""
def run():
    import json,os
    from PyQt6 import sip
    from PyQt6.QtWidgets import QWidget,QApplication
    from PyQt6.QtCore import Qt,QPoint,QPointF,QEvent
    from PyQt6.QtGui import QMouseEvent
    from core.config_manager import config_mgr
    from core.i18n import I18n
    from core.timer_policy import TimerSession,migrate_preferences
    from core.timer_fixes import controller
    from core.window_tracker import WindowInfo
    from ui.pet_widget import PetWidget
    from ui.timer_widget import TimerWidget
    from ui.settings.tab_pet import PetCardWidget
    old_config,old_language=config_mgr.config,I18n.get_lang()
    old_providers=(controller.foreground,controller.idle,controller.allowed,controller.clock,controller.session)
    made=[];passed=[];timers=[]
    now=[0.0];idle=[0.0];front=[None]
    try:
        config_mgr.config={'settings':{'magnetic_snap':True,'snap_distance':15,'clamp_to_screen':False,'dark_mode':False},
            'groups':{'work':['ChatGPT','Logseq'],'social':['QQ','微信']},
            'timers':[dict(id='work',name='Work',group='work',idle_timeout=60,elapsed_seconds=100,x=300,y=312),
                      dict(id='social',name='Social',group='social',idle_timeout=60,elapsed_seconds=20,x=300,y=312)],
            'pets':[dict(id='pet',skin='羿',bound_timer_id='social',x=100,y=100,scale=1)]}
        migrate_preferences(config_mgr.config)
        controller.session=TimerSession('social')
        controller.foreground=lambda:front[0]
        controller.idle=lambda:idle[0]
        controller.allowed=lambda:True
        controller.clock=lambda:now[0]
        def info(app,aliases=None,title=''):
            result=WindowInfo(title=title,app_name=app,window_id=999,pid=os.getpid()+100)
            result.aliases=aliases or (app,)
            return result
        class ProbePet(PetWidget):
            def __init__(self):
                QWidget.__init__(self)
                self.pet_data=config_mgr.config['pets'][0]
                self.get_all_timers_callback=lambda:timers
                self.drag_position=QPoint()
                self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
                self.resize(544,432);self.move(100,100);self.show()
            def paintEvent(self,event):pass
        pet=ProbePet();made.append(pet)
        bound=lambda timer_id:pet if pet.pet_data.get('bound_timer_id')==timer_id else None
        for data in config_mgr.config['timers']:
            timer=TimerWidget(data,lambda:timers,bound,lambda:None)
            made.append(timer);timers.append(timer)
            timer.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);timer.show()
        work,social=timers
        front[0]=info('ChatGPT');controller.step()
        assert work.isVisible() and not social.isVisible()
        assert pet.pet_data['bound_timer_id']=='work'
        assert set(pet.pet_data['bound_timer_ids'])=={'work','social'}
        passed.append('one visible work card and both associations retained')
        now[0]=1;controller.step();assert work.timer_data['elapsed_seconds']==101
        idle[0]=120;front[0]=info('QQ',title='ChatGPT discussion');now[0]=2;controller.step()
        assert social.isVisible() and not work.isVisible()
        assert controller.session.reason=='idle' and pet.pet_data['bound_timer_id']=='social'
        assert work.timer_data['elapsed_seconds']==101
        passed.append('QQ switches card while idle without charging work')
        idle[0]=0;now[0]=3;controller.step();now[0]=4;controller.step()
        assert social.timer_data['elapsed_seconds']==21
        front[0]=info('WeChat',('WeChat','微信'));now[0]=5;controller.step()
        assert social.timer_data['elapsed_seconds']==22 and work.timer_data['elapsed_seconds']==101
        passed.append('WeChat aliases count social only')
        front[0]=info('Finder');now[0]=6;controller.step()
        assert social.isVisible() and not work.isVisible() and controller.session.reason=='unmatched'
        assert social.timer_data['elapsed_seconds']==22
        front[0]=WindowInfo();now[0]=7;controller.step()
        assert controller.session.reason=='unavailable' and controller.engine.current_app_name==''
        assert social.timer_data['elapsed_seconds']==22
        passed.append('unmatched and failed reads retain last card without stale counting')
        front[0]=info('ChatGPT');now[0]=8;controller.step()
        assert pet.pet_data['bound_timer_id']=='work' and work.pos()==social.pos()
        start=work.label_time.mapToGlobal(QPoint(5,5));end=start+QPoint(80,30)
        def mouse(kind,global_pos,button,buttons):
            return QMouseEvent(kind,QPointF(work.label_time.mapFromGlobal(global_pos)),QPointF(global_pos),button,buttons,Qt.KeyboardModifier.NoModifier)
        for kind,pos,button,buttons in [(QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton),
            (QEvent.Type.MouseMove,end,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton),
            (QEvent.Type.MouseButtonRelease,end,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)]:
            QApplication.sendEvent(work.label_time,mouse(kind,pos,button,buttons))
        controller.refresh_widgets()
        assert pet.pos()==QPoint(180,130),pet.pos()
        assert work.pos()==social.pos() and not social.isVisible()
        passed.append('dragging visible timer moves pet and both shared anchors')
        pet.unbind_timer();assert pet.pet_data['bound_timer_ids']==[]
        pet.bind_to_timer('work');pet.bind_to_timer('social')
        assert set(pet.pet_data['bound_timer_ids'])=={'work','social'}
        assert work.isVisible() and not social.isVisible()
        I18n.set_language('zh_CN')
        card=PetCardWidget(pet.pet_data,lambda data:None);made.append(card)
        assert card.bound_combo.currentData()=='__multiple__'
        card.bound_combo.setCurrentIndex(card.bound_combo.findData('__all__'))
        assert pet.pet_data['follow_current_timer']
        assert controller.session.reason=='counting'
        passed.append('additive associations and follow-all setting work without displaying two cards')
        saved_allowed=controller.allowed
        def failed_permission():raise RuntimeError('probe')
        controller.allowed=failed_permission
        assert not controller.is_active('work')
        controller.allowed=saved_allowed
        passed.append('activity gating fails closed if a provider raises')
        return {'passed':passed,'work_seconds':work.timer_data['elapsed_seconds'],'social_seconds':social.timer_data['elapsed_seconds']}
    finally:
        for widget in reversed(made):
            if not sip.isdeleted(widget):widget.hide();sip.delete(widget)
        config_mgr.config=old_config
        controller.foreground,controller.idle,controller.allowed,controller.clock,controller.session=old_providers
        I18n.set_language(old_language)
