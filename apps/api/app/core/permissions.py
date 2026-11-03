from enum import StrEnum
class Action(StrEnum):
    READ="read"
    DRAFT="draft"
    SEND_EMAIL="send_email"
    SUBMIT_APPLICATION="submit_application"

def action_allowed(action: Action, approved: bool=False, enabled: bool=False) -> bool:
    if action in {Action.SEND_EMAIL, Action.SUBMIT_APPLICATION}:
        return approved and enabled
    return True
