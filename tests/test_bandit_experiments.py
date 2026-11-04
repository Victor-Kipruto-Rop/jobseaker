from packages.recommendations.bandit_experiments import assign_arm, evaluate_experiment

def test_candidate_assignment_is_stable_and_balanced():
    a = assign_arm(17, "feed-v1", ["control", "explore"], "test-secret")
    b = assign_arm(17, "feed-v1", ["control", "explore"], "test-secret")
    assert a == b
    assert a["assignment_unit"] == "candidate"
    assert a["propensity"] == 0.5

def test_experiment_requires_minimum_exposure_before_decision():
    events = [{"arm": "control", "event_type": "impression"},
              {"arm": "control", "event_type": "click"}]
    result = evaluate_experiment(events, ["control", "explore"], min_impressions=10)
    assert result["decision"] == "insufficient_exposure"
    assert result["automatic_promotion"] is False

def test_experiment_reports_guarded_arm_metrics():
    events = ([{"arm": "control", "event_type": "impression"}] * 20
              + [{"arm": "control", "event_type": "click"}] * 4
              + [{"arm": "explore", "event_type": "impression"}] * 20
              + [{"arm": "explore", "event_type": "apply"}] * 2)
    result = evaluate_experiment(events, ["control", "explore"], min_impressions=10)
    assert result["arms"]["control"]["ctr"] == 0.2
    assert result["arms"]["explore"]["apply_rate"] == 0.1
    assert result["automatic_promotion"] is False
