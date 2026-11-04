import pytest
from packages.events.replay import replay_published_events

@pytest.mark.asyncio
async def test_replay_requires_explicit_confirmation():
    with pytest.raises(PermissionError):
        await replay_published_events(None, None, topic="user.activity",
                                      event_ids=["123"], confirm=False)
