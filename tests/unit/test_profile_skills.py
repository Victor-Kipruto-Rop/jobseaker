import pytest
from pydantic import ValidationError
from apps.api.app.api.v1.profile.routes import SkillInput

def test_skill_input_preserves_candidate_evidence():
    item = SkillInput(skill_name="  Python  ", proficiency="advanced", evidence="Built a production ETL pipeline")
    assert item.skill_name == "Python"
    assert item.proficiency == "advanced"
    assert item.evidence.startswith("Built")

def test_skill_input_rejects_unknown_proficiency():
    with pytest.raises(ValidationError):
        SkillInput(skill_name="Python", proficiency="guru")

def test_skill_input_rejects_blank_name():
    with pytest.raises(ValidationError):
        SkillInput(skill_name="   ")
