"""Real HTTP/Redis smoke test. Run inside the local Docker test network."""
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import urlopen

BASE = os.getenv("BASE_URL", "http://frontend:8080")


def get(path, status=200):
    try:
        response = urlopen(BASE + path, timeout=16)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read().decode()
        assert response.status == status, (path, response.status, body)
        return body


assert "EKS Debug Lab" in get("/")
assert "makeRequest" in get("/app.js")
assert "color-scheme" in get("/styles.css")
info = json.loads(get("/api/info"))
assert info["redis"] == "connected"
assert info["namespace"] == "local"
assert json.loads(get("/api/error", 500))["error"] == "intentional_lab_error"
before = json.loads(get("/api/cache?increment=false"))["counter"]
assert json.loads(get("/api/cache"))["counter"] == before + 1
assert json.loads(get("/api/cache?increment=false"))["counter"] == before + 1
start = time.monotonic()
get("/api/slow?seconds=1")
assert time.monotonic() - start >= 1
get("/api/slow?seconds=11", 422)
cpu = json.loads(get("/api/cpu?seconds=1"))
assert 1 <= cpu["duration_seconds"] < 4
get("/api/cpu?seconds=6", 422)
print("PASS: frontend → API → Redis; static assets, identity, counter, 500, delay and CPU bounds")
