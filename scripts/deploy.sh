#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Contexto: $(kubectl config current-context)"
kubectl apply -k "$ROOT/k8s/overlays/dev"
