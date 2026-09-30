#!/usr/bin/env bash
set -euo pipefail
version="${KUBECTL_VERSION:-v1.35.0}"
[[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 1
case "$(uname -m)" in
  x86_64) arch=amd64 ;;
  aarch64|arm64) arch=arm64 ;;
  *) echo 'Unsupported Linux architecture' >&2; exit 1 ;;
esac
[[ "$(uname -s)" == Linux ]] || { echo 'This installer requires Linux' >&2; exit 1; }
directory="${RUNNER_TEMP:-/tmp}/eks-lab-tools"
mkdir -p "$directory"
curl -fsSL "https://dl.k8s.io/release/$version/bin/linux/$arch/kubectl" -o "$directory/kubectl"
curl -fsSL "https://dl.k8s.io/release/$version/bin/linux/$arch/kubectl.sha256" -o "$directory/kubectl.sha256"
echo "$(cat "$directory/kubectl.sha256")  $directory/kubectl" | sha256sum --check
chmod +x "$directory/kubectl"
if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "$directory" >> "$GITHUB_PATH"
fi
"$directory/kubectl" version --client
