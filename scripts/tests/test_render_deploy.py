import importlib.util
import unittest
from pathlib import Path

import yaml

spec = importlib.util.spec_from_file_location("render_deploy", Path(__file__).resolve().parents[1] / "render-deploy.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class DeployRenderingTests(unittest.TestCase):
    def test_exact_digests_and_namespace_boundary(self):
        frontend = "123456789012.dkr.ecr.us-east-1.amazonaws.com/eks-lab-dev/app@sha256:" + "a" * 64
        api = "123456789012.dkr.ecr.us-east-1.amazonaws.com/eks-lab-dev/app@sha256:" + "b" * 64
        resources = list(yaml.safe_load_all(renderer.render(frontend, api)))
        self.assertEqual(len(resources), 6)
        self.assertTrue(all(r["metadata"]["namespace"] == "lab-dev" for r in resources))
        self.assertFalse(any(r["kind"] == "Namespace" for r in resources))
        deployments = {r["metadata"]["name"]: r for r in resources if r["kind"] == "Deployment"}
        for name, expected in [("frontend", frontend), ("api", api)]:
            self.assertEqual(deployments[name]["spec"]["template"]["spec"]["containers"][0]["image"], expected)
        self.assertEqual({n: d["spec"]["replicas"] for n, d in deployments.items()}, {"frontend": 2, "api": 2, "redis": 1})
        self.assertTrue(all(r["spec"]["type"] == "ClusterIP" for r in resources if r["kind"] == "Service"))

    def test_reject_mutable_tags_and_invalid_digests(self):
        for value in ["repo:latest", "repo:1.0.0", "repo@sha256:abc", "repo@sha256:" + "g" * 64, "repo\n@sha256:" + "a" * 64]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                renderer.image_parts(value)


if __name__ == "__main__":
    unittest.main()
