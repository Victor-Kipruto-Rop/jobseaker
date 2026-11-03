from apps.api.app.core.permissions import Action,action_allowed
def test_external_actions_require_approval_and_enablement():
    assert not action_allowed(Action.SEND_EMAIL,False,True)
    assert not action_allowed(Action.SUBMIT_APPLICATION,True,False)
    assert action_allowed(Action.SEND_EMAIL,True,True)
