"""Small, deliberately explicit API for learning Kubernetes troubleshooting."""

import asyncio
import os
import socket
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Do not fail startup if Redis is down: /health must still work.
    app.state.redis = Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
        retry=Retry(NoBackoff(), 0),
        max_connections=20,
    )
    app.state.requests = 0
    app.state.cpu_lock = threading.Lock()
    yield
    await app.state.redis.aclose()


app = FastAPI(title="EKS Debug Lab API", version="1.0.0", lifespan=lifespan)
CACHE_KEY = "eks-debug-lab:cache-counter"


def pod_info():
    return {
        "hostname": os.getenv("POD_NAME", socket.gethostname()),
        "namespace": os.getenv("POD_NAMESPACE", "local"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.middleware("http")
async def count_requests(request: Request, call_next):
    # One Uvicorn worker per Pod. Health probes do not affect the counter.
    if request.url.path.startswith("/api/"):
        request.app.state.requests += 1
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-API-Pod"] = pod_info()["hostname"]
    return response


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    return JSONResponse(status_code=503, content={
        "status": "unavailable", "redis": "disconnected",
        "message": "Redis indisponível. Verifique o Pod, Service e DNS.",
        **pod_info(),
    })


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready(request: Request):
    await request.app.state.redis.ping()
    return {"status": "ready", "redis": "connected"}


@app.get("/api/info")
async def info(request: Request):
    try:
        await request.app.state.redis.ping()
        redis_status = "connected"
    except RedisError:
        redis_status = "disconnected"
    return {
        "service": "eks-debug-api",
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "status": "healthy" if redis_status == "connected" else "degraded",
        **pod_info(),
        "redis": redis_status,
        "requests": request.app.state.requests,
    }


@app.get("/api/cache")
async def cache(request: Request, increment: bool = True):
    redis = request.app.state.redis
    if increment:
        count = await redis.incr(CACHE_KEY)
    else:
        count = int(await redis.get(CACHE_KEY) or 0)
    return {"redis": "connected", "counter": count, **pod_info()}


@app.get("/api/error")
async def intentional_error():
    return JSONResponse(status_code=500, content={
        "error": "intentional_lab_error",
        "message": "Erro HTTP 500 intencional do laboratório.",
        **pod_info(),
    })


@app.get("/api/slow")
async def slow(seconds: Annotated[int, Query(ge=1, le=10)] = 3):
    await asyncio.sleep(seconds)
    return {"status": "ok", "delay_seconds": seconds, **pod_info()}


@app.get("/api/cpu")
def cpu(request: Request, seconds: Annotated[int, Query(ge=1, le=5)] = 2):
    # A sync route runs in a thread, keeping the event loop available for probes.
    # Only one CPU experiment per Pod at a time; wall time bounds throttled runs.
    lock = request.app.state.cpu_lock
    if not lock.acquire(blocking=False):
        return JSONResponse(status_code=429, content={
            "error": "cpu_test_busy", "message": "Já existe um teste neste Pod."
        })
    try:
        start = time.monotonic()
        iterations = 0
        while time.monotonic() - start < seconds:
            sum(i * i for i in range(1000))
            iterations += 1
        return {
            "status": "ok", "duration_seconds": round(time.monotonic() - start, 3),
            "iterations": iterations, **pod_info(),
        }
    finally:
        lock.release()
