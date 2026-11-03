from packages.automation.approvals.service import create_approval
def require_approval(action_type:str,payload:dict,rationale:str)->dict:
    return create_approval(action_type,payload,rationale)
