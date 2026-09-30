import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from app.main import app


class FakeRedis:
    def __init__(self):
        self.counter = 0
        self.available = True

    async def ping(self):
        if not self.available:
            raise ConnectionError("Redis offline")
        return True

    async def incr(self, key):
        await self.ping()
        self.counter += 1
        return self.counter

    async def get(self, key):
        await self.ping()
        return str(self.counter)

    async def aclose(self):
        pass


@pytest.fixture
def client(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr("app.main.Redis.from_url", lambda *args, **kwargs: redis)
    monkeypatch.setenv("POD_NAME", "api-test-pod")
    monkeypatch.setenv("POD_NAMESPACE", "lab-dev")
    with TestClient(app) as client:
        yield client


def test_health_and_ready(client):
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/ready").status_code == 200
    assert app.state.requests == 0


def test_info_identity_and_counter(client):
    first = client.get("/api/info")
    assert first.json()["hostname"] == "api-test-pod"
    assert first.json()["namespace"] == "lab-dev"
    assert first.json()["version"] == "1.0.0"
    assert first.json()["redis"] == "connected"
    assert first.json()["requests"] == 1
    assert first.headers["x-api-pod"] == "api-test-pod"
    assert first.headers["cache-control"] == "no-store"
    assert client.get("/api/info").json()["requests"] == 2


def test_cache_increment_and_read(client):
    assert client.get("/api/cache?increment=false").json()["counter"] == 0
    assert client.get("/api/cache").json()["counter"] == 1
    assert client.get("/api/cache").json()["counter"] == 2
    assert client.get("/api/cache?increment=false").json()["counter"] == 2


def test_redis_outage_and_recovery(client):
    app.state.redis.available = False
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    assert client.get("/api/cache").status_code == 503
    assert client.get("/api/info").json()["status"] == "degraded"
    app.state.redis.available = True
    assert client.get("/ready").status_code == 200


def test_intentional_error(client):
    response = client.get("/api/error")
    assert response.status_code == 500
    assert response.json()["error"] == "intentional_lab_error"
    assert app.state.requests == 1
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("endpoint,seconds", [
    ("slow", "0"), ("slow", "11"), ("slow", "-1"), ("slow", "1.5"),
    ("slow", "NaN"), ("cpu", "0"), ("cpu", "6"), ("cpu", "inf"),
])
def test_duration_limits(client, endpoint, seconds):
    assert client.get(f"/api/{endpoint}?seconds={seconds}").status_code == 422


def test_slow_request(client):
    start = time.monotonic()
    assert client.get("/api/slow?seconds=1").json()["delay_seconds"] == 1
    assert 1 <= time.monotonic() - start < 4


def test_cpu_is_bounded_and_probes_remain_available(client):
    with ThreadPoolExecutor() as executor:
        job = executor.submit(client.get, "/api/cpu?seconds=1")
        deadline = time.monotonic() + 2
        while not app.state.cpu_lock.locked() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert app.state.cpu_lock.locked()
        assert client.get("/api/cpu?seconds=1").status_code == 429
        assert client.get("/health").status_code == 200
        result = job.result(timeout=5)
    assert result.status_code == 200
    assert 1 <= result.json()["duration_seconds"] < 4
    assert result.json()["iterations"] > 0
    assert not app.state.cpu_lock.locked()


def test_counter_resets_on_restart(monkeypatch):
    monkeypatch.setattr("app.main.Redis.from_url", lambda *args, **kwargs: FakeRedis())
    for _ in range(2):
        with TestClient(app) as restarted:
            assert restarted.get("/api/info").json()["requests"] == 1
