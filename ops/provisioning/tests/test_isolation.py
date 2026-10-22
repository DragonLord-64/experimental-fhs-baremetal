"""Guard the preparation fixture's physical infrastructure boundary."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IsolationTests(unittest.TestCase):
    def test_only_internal_network_and_empty_inventory(self):
        config = json.loads((ROOT / "compose.json").read_text())
        self.assertEqual(config["networks"], {
            "provisioning": {"driver": "bridge", "internal": True}})
        self.assertEqual(json.loads((ROOT / "nodes.json").read_text()), {})
        self.assertEqual(list(config["services"]), ["bifrost-prep"])

    def test_no_host_access_or_service_startup(self):
        service = json.loads((ROOT / "compose.json").read_text())["services"]["bifrost-prep"]
        for forbidden in ("privileged", "network_mode", "pid", "ipc", "devices",
                          "ports", "build", "cap_add", "cgroup", "extra_hosts"):
            self.assertNotIn(forbidden, service)
        self.assertEqual(service["cap_drop"], ["ALL"])
        self.assertEqual(service["security_opt"], ["no-new-privileges:true"])
        self.assertTrue(service["read_only"])
        self.assertEqual(service["user"], "65534:65534")
        self.assertEqual(service["volumes"], [{"type": "bind", "source": "./nodes.json",
                         "target": "/lab/nodes.json", "read_only": True}])
        self.assertEqual(service["entrypoint"], ["/bin/sh", "-ec"])
        self.assertEqual(service["command"], ["trap 'exit 0' TERM INT; while :; do sleep 30 & wait $!; done"])
        self.assertEqual(service["pull_policy"], "never")


if __name__ == "__main__":
    unittest.main()
