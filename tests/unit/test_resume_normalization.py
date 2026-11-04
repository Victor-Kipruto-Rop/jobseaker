import pytest
from fastapi import HTTPException

from apps.api.app.api.v1.resumes.routes import extract_text


def test_markdown_and_plain_text_resume_normalization():
    markdown, markdown_type = extract_text("resume.md", b"# Data Engineer\r\n\r\nPython, SQL and Kafka.")
    plain, plain_type = extract_text("resume.txt", b"Victor Kipruto\r\nData Engineer")
    assert markdown_type == "text/markdown"
    assert markdown.startswith("# Data Engineer\n")
    assert plain_type == "text/plain"
    assert plain == "Victor Kipruto\nData Engineer"


def test_text_resume_rejects_invalid_utf8():
    with pytest.raises(HTTPException) as error:
        extract_text("resume.txt", b"\xff\xfe\xfa")
    assert error.value.status_code == 400
