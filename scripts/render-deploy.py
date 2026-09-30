"""Render namespaced application resources using Kustomize and immutable images."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def image_parts(image):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9./:_-]*@sha256:[a-f0-9]{64}", image):
        raise ValueError("Use a full registry/repository@sha256:<64 hex characters> image reference")
    return image.split("@", 1)


def render(frontend_image, api_image):
    images = []
    for name, image in [("frontend", frontend_image), ("api", api_image)]:
        repository, digest = image_parts(image)
        images.append({"name": f"eks-debug-lab-{name}", "newName": repository, "digest": digest})
    # A sibling overlay keeps relative paths inside Kustomize's normal load rules.
    with tempfile.TemporaryDirectory(prefix=".deploy-", dir=ROOT / "k8s/overlays") as directory:
        config = {"apiVersion": "kustomize.config.k8s.io/v1beta1", "kind": "Kustomization",
                  "resources": ["../dev"], "images": images}
        Path(directory, "kustomization.yaml").write_text(json.dumps(config))
        rendered = subprocess.check_output(["kubectl", "kustomize", directory], text=True)
    resources = [r for r in yaml.safe_load_all(rendered) if r and r["kind"] != "Namespace"]
    expected = {(kind, name) for kind in ["Deployment", "Service"] for name in ["frontend", "api", "redis"]}
    actual = {(r["kind"], r["metadata"]["name"]) for r in resources}
    if actual != expected or len(resources) != 6:
        raise ValueError("Deploy must contain exactly the three application Deployments and Services")
    for resource in resources:
        if resource["metadata"].get("namespace") != "lab-dev":
            raise ValueError("All deployed resources must belong to lab-dev")
    deployments = {r["metadata"]["name"]: r for r in resources if r["kind"] == "Deployment"}
    for name, image in [("frontend", frontend_image), ("api", api_image)]:
        actual_image = deployments[name]["spec"]["template"]["spec"]["containers"][0]["image"]
        if actual_image != image:
            raise ValueError(f"Kustomize did not set the expected {name} digest: {actual_image}")
    return yaml.safe_dump_all(resources, sort_keys=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-image", required=True)
    parser.add_argument("--api-image", required=True)
    args = parser.parse_args()
    try:
        sys.stdout.write(render(args.frontend_image, args.api_image))
    except (ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")
