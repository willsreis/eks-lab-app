#!/usr/bin/env bash
set -euo pipefail
exec kubectl port-forward --address 127.0.0.1 -n lab-dev svc/frontend "${1:-8080}:80"
