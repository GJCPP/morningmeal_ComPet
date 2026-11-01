import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'morningmeal_Compet_V3'))
from core.timer_policy import TimerSession, associated_ids, migrate_preferences, select_timer


def config():
    return {'settings':{},'groups':{'work':['Logseq','ChatGPT'],'social':['QQ','微信']},
            'timers':[{'id':'work','group':'work','idle_timeout':60,'elapsed_seconds':100},
                      {'id':'social','group':'social','idle_timeout':60,'elapsed_seconds':20}],
            'pets':[{'id':'pet','bound_timer_id':'social','x':10,'y':20}]}


class TimerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.data=config();self.session=TimerSession('work')
    def step(self,app,now,idle=0,**kwargs):
        return self.session.step(self.data,[app],'',idle,now,**kwargs)
    def test_work_to_qq_does_not_charge_work(self):
        self.step('ChatGPT',0);self.step('ChatGPT',1)
        self.step('QQ',2);self.step('QQ',3)
        self.assertEqual([t['elapsed_seconds'] for t in self.data['timers']],[101,21])
        self.assertEqual(self.session.display_id,'social')
    def test_switch_is_detected_while_idle(self):
        self.step('Logseq',0)
        self.step('QQ',1,idle=120)
        self.assertEqual(self.session.matched_id,'social')
        self.assertEqual(self.session.display_id,'social')
        self.assertEqual(self.session.reason,'idle')
        self.assertEqual(self.data['timers'][0]['elapsed_seconds'],100)
    def test_exact_app_beats_chat_topic_title(self):
        self.assertEqual(select_timer(self.data['timers'],self.data['groups'],['QQ'],'ChatGPT discussion','work'),'social')
    def test_wechat_alias_matches_chinese_keyword(self):
        self.assertEqual(select_timer(self.data['timers'],self.data['groups'],['WeChat','微信'],'','work'),'social')
    def test_title_matching_still_supported(self):
        self.assertEqual(select_timer(self.data['timers'],self.data['groups'],['Firefox'],'ChatGPT — browser'),'work')
    def test_unknown_app_retains_recent_without_counting(self):
        self.step('QQ',0);self.step('Finder',1);self.step('Finder',2)
        self.assertEqual(self.session.display_id,'social')
        self.assertIsNone(self.session.matched_id)
        self.assertEqual(self.session.reason,'unmatched')
        self.assertEqual(self.data['timers'][1]['elapsed_seconds'],20)
    def test_query_failure_never_reuses_old_app(self):
        self.step('ChatGPT',0)
        self.step('ChatGPT',1,available=False)
        self.assertIsNone(self.session.matched_id)
        self.assertEqual(self.session.reason,'unavailable')
        self.assertEqual(self.data['timers'][0]['elapsed_seconds'],100)
    def test_paused_timer_is_shown_without_counting(self):
        self.data['timers'][1]['paused']=True
        self.step('QQ',0);self.step('QQ',1)
        self.assertEqual(self.session.display_id,'social')
        self.assertEqual(self.session.reason,'paused')
        self.assertEqual(self.data['timers'][1]['elapsed_seconds'],20)
    def test_subsecond_polls_accumulate_real_elapsed_time(self):
        for n in range(11):self.step('ChatGPT',n/5)
        self.assertEqual(self.data['timers'][0]['elapsed_seconds'],102)
    def test_sleep_gap_not_charged(self):
        self.step('Logseq',0);self.step('Logseq',100)
        self.assertEqual(self.data['timers'][0]['elapsed_seconds'],100)
    def test_permission_missing_does_not_prevent_selection(self):
        self.step('QQ',0,allowed=False)
        self.assertEqual(self.session.display_id,'social')
        self.assertEqual(self.session.reason,'permission')
    def test_overlapping_groups_choose_only_one(self):
        self.data['groups']['social']=['ChatGPT']
        self.step('ChatGPT',0);result=self.step('ChatGPT',1)
        self.assertEqual(result,{'work':101})
        self.assertEqual(self.data['timers'][1]['elapsed_seconds'],20)
    def test_single_pet_migrates_to_both_timers(self):
        before=copy.deepcopy(self.data['timers'])
        self.assertTrue(migrate_preferences(self.data))
        self.assertEqual(self.data['pets'][0]['bound_timer_ids'],['work','social'])
        self.assertTrue(self.data['pets'][0]['follow_current_timer'])
        self.assertEqual(self.data['timers'],before)
        self.assertFalse(migrate_preferences(self.data))
    def test_explicit_unlink_is_preserved(self):
        self.data['pets'][0].update(bound_timer_ids=[],follow_current_timer=False,bound_timer_id='work')
        migrate_preferences(self.data)
        self.assertEqual(associated_ids(self.data['pets'][0],self.data['timers']),[])
    def test_follow_all_includes_future_timer(self):
        migrate_preferences(self.data)
        self.data['timers'].append({'id':'reading'})
        self.assertEqual(associated_ids(self.data['pets'][0],self.data['timers']),['work','social','reading'])
    def test_removed_recent_timer_falls_back_to_remaining_timer(self):
        self.session.display_id='deleted';self.data['timers']=self.data['timers'][:1]
        self.step('Finder',0)
        self.assertEqual(self.session.display_id,'work')

if __name__=='__main__':unittest.main()
