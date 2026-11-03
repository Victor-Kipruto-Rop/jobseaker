import asyncio
import pytest
from packages.automation import tasks

@pytest.mark.asyncio
async def test_saved_search_fetch_uses_bounded_concurrency(monkeypatch):
    active = 0
    maximum = 0

    async def fake_greenhouse(board, limit):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return [{"title": board}]

    monkeypatch.setattr(tasks, "discover_greenhouse", fake_greenhouse)
    searches = [(index, index, {"source": "greenhouse", "board": f"board-{index}"})
                for index in range(8)]
    results = await tasks._fetch_saved_searches(searches, concurrency=2)
    assert len(results) == 8
    assert maximum == 2
    assert all(items and error is None for _, _, _, items, error in results)

@pytest.mark.asyncio
async def test_saved_search_fetch_isolates_source_failures(monkeypatch):
    async def fake_greenhouse(board, limit):
        if board == "broken":
            raise RuntimeError("upstream unavailable")
        return [{"title": board}]

    monkeypatch.setattr(tasks, "discover_greenhouse", fake_greenhouse)
    searches = [
        (1, 1, {"source": "greenhouse", "board": "healthy"}),
        (2, 2, {"source": "greenhouse", "board": "broken"}),
    ]
    results = await tasks._fetch_saved_searches(searches)
    assert results[0][3] == [{"title": "healthy"}]
    assert results[0][4] is None
    assert results[1][3] == []
    assert isinstance(results[1][4], RuntimeError)
