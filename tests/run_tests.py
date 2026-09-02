"""
Custom Test Runner for Shuttle Flux test suite.
"""

import sys
import os
import traceback

# Ensure root workspace is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from tests.unit.test_movement import (
    test_get_court_zone,
    test_smooth_court_trajectory,
    test_compute_distance_meters,
    test_compute_speed_profile,
    test_compute_speed_profile_uses_real_timestamps,
)
from tests.unit.test_homography import test_homography_square_to_square
from tests.unit.test_rally import (
    test_rally_segmenter_basic,
    test_rally_segmenter_uses_timestamps_for_sampled_frames,
)
from tests.integration.test_full_pipeline import test_full_pipeline_analytics_contract
from tests.integration.test_api import test_api_root_and_health, test_api_demo_match


def run_all_tests():
    test_functions = [
        ("test_get_court_zone", test_get_court_zone),
        ("test_smooth_court_trajectory", test_smooth_court_trajectory),
        ("test_compute_distance_meters", test_compute_distance_meters),
        ("test_compute_speed_profile", test_compute_speed_profile),
        ("test_compute_speed_profile_uses_real_timestamps", test_compute_speed_profile_uses_real_timestamps),
        ("test_homography_square_to_square", test_homography_square_to_square),
        ("test_rally_segmenter_basic", test_rally_segmenter_basic),
        ("test_rally_segmenter_uses_timestamps_for_sampled_frames", test_rally_segmenter_uses_timestamps_for_sampled_frames),
        ("test_full_pipeline_analytics_contract", test_full_pipeline_analytics_contract),
        ("test_api_root_and_health", test_api_root_and_health),
        ("test_api_demo_match", test_api_demo_match),
    ]

    print("=" * 60)
    print("RUNNING SHUTTLE FLUX COMPLETE TEST SUITE")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, func in test_functions:
        try:
            func()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            traceback.print_exc()
            failed += 1

    print("-" * 60)
    print(f"Summary: {passed} passed, {failed} failed out of {len(test_functions)} tests.")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
