#!/usr/bin/env bash
set -euo pipefail
kubectl get pods -n lab-dev
kubectl get deployments -n lab-dev
kubectl get svc -n lab-dev
