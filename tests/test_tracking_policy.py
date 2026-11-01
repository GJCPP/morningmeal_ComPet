"""Selection and accounting for overlapping groups and the fallback timer."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'morningmeal_Compet_V3'))
from core.timer_policy import TimerSession, matching_timer_ids, has_fallback_timer


def settings():
    return {'settings': {}, 'groups': {'work': ['Editor', 'Browser'], 'study': ['Editor']},
            'timers': [{'id': 'work', 'group': 'work', 'idle_timeout': 60, 'elapsed_seconds': 10},
                       {'id': 'study', 'group': 'study', 'idle_timeout': 5, 'elapsed_seconds': 20},
                       {'id': 'other', 'is_fallback': True, 'idle_timeout': 60, 'elapsed_seconds': 30}]}


class TrackingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.data = settings()
        self.session = TimerSession('study')

    def step(self, app, now, idle=0, **kwargs):
        return self.session.step(self.data, [app], '', idle, now, **kwargs)

    def test_overlap_counts_both_and_displays_first_instead_of_recent(self):
        self.step('Editor', 0)
        self.assertEqual(self.step('Editor', 1), {'work': 11, 'study': 21})
        self.assertEqual(self.session.display_id, 'work')
        self.assertEqual(self.session.matched_ids, ['work', 'study'])
        self.assertEqual(self.data['timers'][2]['elapsed_seconds'], 30)

    def test_reordering_changes_display_but_not_accounting(self):
        self.data['timers'][:2] = reversed(self.data['timers'][:2])
        self.step('Editor', 0)
        self.assertEqual(self.step('Editor', 1), {'study': 21, 'work': 11})
        self.assertEqual(self.session.display_id, 'study')

    def test_new_overlap_is_not_charged_for_previous_interval(self):
        self.step('Browser', 0)
        self.assertEqual(self.step('Editor', 1), {'work': 11})
        self.assertEqual(self.step('Editor', 2), {'work': 12, 'study': 21})

    def test_overlap_uses_each_timers_idle_threshold(self):
        self.step('Editor', 0, idle=10)
        self.assertEqual(self.step('Editor', 1, idle=10), {'work': 11})
        self.assertEqual(self.session.counting_ids, {'work'})

    def test_paused_ordinary_match_is_not_redirected_to_other(self):
        self.data['timers'][0]['paused'] = True
        self.step('Browser', 0)
        self.assertEqual(self.step('Browser', 1), {})
        self.assertEqual(self.session.matched_id, 'work')
        self.assertEqual(self.session.reason, 'paused')

    def test_first_paused_match_stays_displayed_while_another_counts(self):
        self.data['timers'][0]['paused'] = True
        self.step('Editor', 0)
        self.assertEqual(self.step('Editor', 1), {'study': 21})
        self.assertEqual(self.session.display_id, 'work')
        self.assertEqual(self.session.reason, 'paused')

    def test_other_counts_only_unmatched_task(self):
        self.step('Unlisted', 0)
        self.assertEqual(self.step('Unlisted', 1), {'other': 31})
        self.assertEqual(self.session.display_id, 'other')
        self.assertEqual(self.step('Editor', 2), {})
        self.assertEqual(self.step('Editor', 3), {'work': 11, 'study': 21})
        self.assertEqual(self.data['timers'][2]['elapsed_seconds'], 31)

    def test_other_never_wins_by_position_or_its_group(self):
        self.data['timers'].insert(0, self.data['timers'].pop())
        self.data['timers'][0]['group'] = 'work'
        self.step('Editor', 0)
        self.assertEqual(self.session.matched_ids, ['work', 'study'])

    def test_other_keeps_idle_pause_and_permission_checks(self):
        for idle, paused, allowed in [(61, False, True), (0, True, True), (0, False, False)]:
            with self.subTest(idle=idle, paused=paused, allowed=allowed):
                self.data['timers'][2]['paused'] = paused
                self.session = TimerSession()
                self.step('Unlisted', 0, idle=idle, allowed=allowed)
                self.assertEqual(self.step('Unlisted', 1, idle=idle, allowed=allowed), {})

    def test_missing_foreground_or_failed_query_does_not_charge_other(self):
        for app, available in [('', True), ('Unlisted', False)]:
            self.session = TimerSession()
            self.step(app, 0, available=available)
            self.assertEqual(self.step(app, 1, available=available), {})
            self.assertEqual(self.session.matched_ids, [])

    def test_other_role_is_explicit_and_survives_rename(self):
        self.data['timers'][2]['name'] = 'Uncategorized'
        self.assertTrue(has_fallback_timer(self.data))
        self.data['timers'].pop()
        self.data['timers'][0]['name'] = 'Other'
        self.assertFalse(has_fallback_timer(self.data))
        self.step('Unlisted', 0)
        self.assertIsNone(self.session.matched_id)

    def test_all_window_slots_are_matched(self):
        self.data['groups']['work'] = ['App' + str(n) for n in range(8)]
        self.assertEqual(matching_timer_ids(self.data['timers'], self.data['groups'], ['App7']), ['work'])

    def test_sleep_does_not_charge_overlapping_or_other_timers(self):
        for app in ['Editor', 'Unlisted']:
            self.session = TimerSession()
            self.step(app, 0)
            self.assertEqual(self.step(app, 100), {})


if __name__ == '__main__':
    unittest.main()
