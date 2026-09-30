#!/usr/bin/env bash
set -euo pipefail
echo "Contexto: $(kubectl config current-context)"
# Preserve the namespace and anything not belonging to this application.
kubectl delete deployment,service -n lab-dev \
  -l app.kubernetes.io/part-of=eks-debug-lab-app --ignore-not-found
