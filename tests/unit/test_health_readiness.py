from contextlib import contextmanager
from apps.api.app.health import routes

class FakeConnection:
    def execute(self, statement):
        return 1

class FakeEngine:
    @contextmanager
    def connect(self):
        yield FakeConnection()

class FakeRedis:
    def ping(self):
        return True
    def close(self):
        return None

def test_readiness_requires_database_and_redis(monkeypatch):
    monkeypatch.setattr(routes, "engine", FakeEngine())
    monkeypatch.setattr(routes.Redis, "from_url", lambda *args, **kwargs: FakeRedis())
    response = routes.ready()
    assert response.status_code == 200

def test_readiness_returns_503_when_dependency_fails(monkeypatch):
    class BrokenEngine:
        @contextmanager
        def connect(self):
            raise RuntimeError("database unavailable")
            yield
    monkeypatch.setattr(routes, "engine", BrokenEngine())
    monkeypatch.setattr(routes.Redis, "from_url", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("redis unavailable")))
    response = routes.ready()
    assert response.status_code == 503

def test_liveness_does_not_depend_on_external_services():
    assert routes.health()["status"] == "ok"
