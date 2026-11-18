import pytest
from game import motion_matching as mod

CASES = [
    ("sample_half", "m.sample_time(30, 60) == approx(0.5)"),
    ("sample_zero", "m.sample_time(0, 60) == approx(0.0)"),
    ("features_three", "m.trajectory_features(2.0, (1.0, 0.0)) == (2.0, 1.0, 0.0)"),
    ("weight_scaled", "m.adaptive_weight(2.0, 0.5) == approx(1.0)"),
    ("weight_high", "m.adaptive_weight(2.0, 1.0) == approx(2.0)"),
    ("penalty_abs", "m.continuity_penalty(1.0, 3.0) == approx(2.0)"),
    ("window_half", "m.blend_window(60, 0.5) == approx(30)"),
    ("strip_root", "m.strip_root_motion((1.0, 2.0), (0.5, 0.5)) == (0.5, 1.5)"),
    ("turn_clamp", "m.turn_transition(2.0, 1.0) == approx(1.0)"),
    ("turn_inside", "m.turn_transition(0.5, 1.0) == approx(0.5)"),
    ("ground_diff", "m.ground_height(5.0, 3.0) == approx(2.0)"),
    ("retarget_double", "m.retarget_scale(1.0, 2.0) == approx(2.0)"),
    ("retarget_zero", "m.retarget_scale(2.0, 2.0) == approx(1.0)"),
    ("frame_half", "m.frame_independent(0.5, 1.0) == approx(0.5)"),
    ("frame_full", "m.frame_independent(1.0, 1.0) == approx(1.0)")
]

@pytest.mark.parametrize("name,expr", CASES, ids=[c[0] for c in CASES])
def test_contract(name, expr):
    assert eval(expr, {"m": mod, "approx": pytest.approx})
