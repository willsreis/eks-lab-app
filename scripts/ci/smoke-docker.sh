#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
prefix="eks-app-ci-${GITHUB_RUN_ID:-local}-$$"
cleanup() {
  docker rm -f -v "$prefix-frontend" "$prefix-api" "$prefix-redis" >/dev/null 2>&1 || true
  docker network rm "$prefix" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$prefix" >/dev/null
docker run -d --name "$prefix-redis" --network "$prefix" --network-alias redis \
  --user 999:999 --read-only --tmpfs /data:uid=999,gid=999,size=128m \
  --cap-drop ALL --security-opt no-new-privileges --memory 128m --cpus 0.25 \
  redis:7.4.5-alpine redis-server --save '' --appendonly no --maxmemory 64mb --maxmemory-policy noeviction >/dev/null
docker run -d --name "$prefix-api" --network "$prefix" --network-alias api \
  --read-only --cap-drop ALL --security-opt no-new-privileges --memory 192m --cpus 0.5 \
  eks-debug-lab-api:1.0.0 >/dev/null
docker run -d --name "$prefix-frontend" --network "$prefix" --network-alias frontend \
  --read-only --tmpfs /tmp:uid=101,gid=101,size=32m --cap-drop ALL \
  --security-opt no-new-privileges --memory 64m --cpus 0.1 eks-debug-lab-frontend:1.0.0 >/dev/null
ready=false
for attempt in {1..30}; do
  if docker exec "$prefix-api" python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/ready", timeout=2)' >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  docker logs "$prefix-api"
  docker logs "$prefix-redis"
  exit 1
fi
docker exec "$prefix-frontend" nginx -c /tmp/nginx.conf -t
docker exec -i "$prefix-api" python < "$ROOT/api/tests/smoke.py"
