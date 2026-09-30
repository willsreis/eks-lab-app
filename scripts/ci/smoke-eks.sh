#!/usr/bin/env bash
set -euo pipefail
log="${RUNNER_TEMP:-/tmp}/eks-app-port-forward-$$.log"
pid=''
cleanup() {
  if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  rm -f -- "$log"
}
trap cleanup EXIT
# The OS selects a free local port, avoiding collisions on a self-hosted runner.
kubectl port-forward --address 127.0.0.1 -n lab-dev svc/frontend :80 > "$log" 2>&1 &
pid=$!
port=''
for attempt in {1..30}; do
  port=$(sed -nE 's/Forwarding from 127\.0\.0\.1:([0-9]+) -> .*/\1/p' "$log" | head -1)
  [[ -n "$port" ]] && break
  kill -0 "$pid" 2>/dev/null || { cat "$log"; exit 1; }
  sleep 1
done
[[ -n "$port" ]] || { cat "$log"; exit 1; }
curl --fail --silent --show-error --max-time 15 "http://127.0.0.1:$port/" >/dev/null
curl --fail --silent --show-error --max-time 15 "http://127.0.0.1:$port/api/info" \
  | jq -e '.service == "eks-debug-api" and .redis == "connected" and .namespace == "lab-dev"'
