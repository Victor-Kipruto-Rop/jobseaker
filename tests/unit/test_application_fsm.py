from packages.applications.fsm import STATUSES, TRANSITIONS, can_transition


def test_application_fsm_rejects_skipping_required_stages():
    assert not can_transition("draft", "submitted")
    assert not can_transition("ready", "offer")
    assert not can_transition("submitted", "accepted")


def test_application_fsm_allows_expected_lifecycle_progression():
    path = ["draft", "ready", "approved", "submitted", "interview", "offer", "accepted", "archived"]
    assert all(can_transition(left, right) for left, right in zip(path, path[1:]))


def test_terminal_application_states_only_archive():
    for state in ("accepted", "rejected", "withdrawn"):
        assert TRANSITIONS[state] == {"archived"}
    assert TRANSITIONS["archived"] == set()
    assert STATUSES == set(TRANSITIONS)
