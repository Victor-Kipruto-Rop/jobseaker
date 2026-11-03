import pytest
from packages.integrations.job_boards.connectors import plain_text, _validate_slug

def test_html_job_description_is_normalized():
    assert plain_text("<p>Python <strong>Data Engineer</strong></p>") == "Python Data Engineer"

def test_board_slug_is_restricted():
    assert _validate_slug("example-board") == "example-board"
    with pytest.raises(ValueError):
        _validate_slug("https://attacker.example/path")
