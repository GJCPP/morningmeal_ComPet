import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'morningmeal_Compet_V3'))
from core.docking import docking_score, snap_timer_rect, timer_position_below_pet


class DockingTests(unittest.TestCase):
    def test_large_pet_uses_bottom_anchor(self):
        pet = (100, 100, 544, 432)
        timer = (302, 528, 140, 70)
        self.assertEqual(docking_score(pet, timer, 15), 0)
        self.assertEqual(timer_position_below_pet(pet, (140, 70)), (302, 528))

    def test_pet_center_over_timer_is_not_enough(self):
        self.assertIsNone(docking_score((100, 100, 544, 432), (302, 316, 140, 70), 15))

    def test_distant_horizontal_pair_does_not_dock(self):
        self.assertIsNone(docking_score((100, 100, 544, 432), (700, 528, 140, 70), 15))

    def test_threshold_and_negative_screen_coordinates(self):
        pet = (-700, 100, 544, 432)
        self.assertEqual(timer_position_below_pet(pet, (140, 70)), (-498, 528))
        self.assertIsNotNone(docking_score(pet, (-498, 543, 140, 70), 15))
        self.assertIsNone(docking_score(pet, (-498, 544, 140, 70), 15))

    def test_adjacent_timer_edges_use_exclusive_bounds(self):
        self.assertEqual(snap_timer_rect((249, 100, 140, 70), [(100, 100, 140, 70)], 15), (240, 100))

    def test_far_orthogonal_timer_does_not_pull_axis(self):
        self.assertEqual(snap_timer_rect((249, 900, 140, 70), [(100, 100, 140, 70)], 15), (249, 900))

    def test_nearest_timer_wins_independent_of_order(self):
        moving = (250, 100, 140, 70)
        others = [(100, 100, 140, 70), (255, 100, 140, 70)]
        self.assertEqual(snap_timer_rect(moving, others, 15), (255, 100))
        self.assertEqual(snap_timer_rect(moving, list(reversed(others)), 15), (255, 100))

if __name__ == '__main__':
    unittest.main()
