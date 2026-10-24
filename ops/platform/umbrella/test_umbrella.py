"""Real pinned-chart renders; no Kubernetes writes or hardware access."""
import base64
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "platform/charts/fhs-platform"
NS = "mid-cbf-monitoring-test"
HOST = "rmdskadevdu011.mda.ca"
RELEASE = "candidate"
spec = importlib.util.spec_from_file_location("acceptance", Path(__file__).with_name("check_manifests.py"))
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


def render(chart=CHART, namespace=NS, prefix="/test", hostname=HOST, extra=(), release=RELEASE):
    cmd = ["helm", "template", release, str(chart), "--namespace", namespace,
           "--set-string", f"global.urlPrefix={prefix}", "--set-string", f"global.hostname={hostname}", *extra]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout, [o for o in yaml.safe_load_all(result.stdout) if o]


def pod_specs(objects):
    for obj in objects:
        if obj["kind"] in ("Deployment", "StatefulSet", "Job"):
            yield obj, obj["spec"]["template"]["spec"]
        elif obj["kind"] == "CronJob":
            yield obj, obj["spec"]["jobTemplate"]["spec"]["template"]["spec"]


def netbox_launch(container):
    """Execute the rendered launch command with only entrypoint/Granian stubbed.

    The pinned image's actual launcher is a fixture: unlike a manifest-only
    assertion, this catches its hardcoded /static route overriding BASE_PATH.
    No NetBox services, image runtime, or network access are needed here.
    """
    entrypoint = "/opt/netbox/docker-entrypoint.sh"
    launcher = "/opt/netbox/launch-netbox.sh"
    command = container.get("command") or [entrypoint]
    args = container.get("args") or ([] if container.get("command") else [launcher])
    if command[0] != entrypoint:
        raise AssertionError("NetBox's initialization entrypoint must still run")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        marker = tmp / "entrypoint-called"
        local_entrypoint = tmp / "docker-entrypoint.sh"
        local_entrypoint.write_text(f'#!/bin/sh\nprintf called > "{marker}"\nexec "$@"\n')
        local_entrypoint.chmod(0o700)
        local_launcher = tmp / "launch-netbox.sh"
        shutil.copyfile(Path(__file__).with_name("fixtures") / "launch-netbox.sh", local_launcher)
        local_launcher.chmod(0o700)
        granian = tmp / "granian"
        granian.write_text(
            "#!/usr/bin/env python3\nimport json, os, sys\n"
            "print(json.dumps({'args': sys.argv[1:], 'port': os.environ.get('GRANIAN_PORT'), "
            "'workers': os.environ.get('GRANIAN_WORKERS')}))\n"
        )
        granian.chmod(0o700)
        argv = [a.replace(entrypoint, str(local_entrypoint)).replace(launcher, str(local_launcher))
                for a in command + args]
        env = {k:v for k,v in os.environ.items() if not k.startswith("GRANIAN_")}
        env["PATH"] = str(tmp) + os.pathsep + env.get("PATH", os.defpath)
        env.update({e["name"]: e["value"] for e in container.get("env", []) if "value" in e})
        result = subprocess.run(argv, env=env, capture_output=True, text=True, check=True, timeout=10)
        if not marker.exists():
            raise AssertionError("NetBox initialization entrypoint did not execute")
        return json.loads(result.stdout)


def last_option(args, name):
    """Read the last occurrence, accepting --option value and --option=value."""
    value = None
    for index, arg in enumerate(args):
        if arg == name:
            value = args[index + 1]
        elif arg.startswith(name + "="):
            value = arg.partition("=")[2]
    return value


class UmbrellaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.objects = render()

    def check_safety(self, text, objects, namespace, hostname, prefix):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as file:
            file.write(text)
            file.flush()
            self.assertEqual([], acceptance.check([file.name], namespace, hostname, prefix))
        self.assertFalse(any(o["kind"] == "PodSecurityPolicy" for o in objects))
        for obj, pod in pod_specs(objects):
            for key in ("hostNetwork", "hostPID", "hostIPC"):
                self.assertFalse(pod.get(key), (obj["metadata"]["name"], key))
            for c in pod.get("containers", []) + pod.get("initContainers", []):
                self.assertFalse(c.get("securityContext", {}).get("privileged"))
                self.assertFalse(any(p.get("hostPort") for p in c.get("ports", [])))
        services = [o for o in objects if o["kind"] == "Service"]
        pods = [o["spec"]["template"]["metadata"].get("labels", {}) for o, _ in pod_specs(objects)
                if o["kind"] in ("Deployment", "StatefulSet")]
        for service in services:
            selector = service["spec"]["selector"]
            self.assertTrue(any(all(p.get(k) == v for k, v in selector.items()) for p in pods), service["metadata"]["name"])
            self.assertFalse(any(p.get("nodePort") for p in service["spec"]["ports"]))
        self.assertNotIn("emulator", json.dumps([o for o in objects if o["kind"] == "ConfigMap" and o["metadata"]["name"] == "fhs-prometheus"]))

    def test_default_is_namespaced_and_backends_resolve(self):
        self.check_safety(self.text, self.objects, NS, HOST, "/test")
        names = {o["metadata"]["name"] for o in self.objects if o["kind"] in ("Deployment", "StatefulSet")}
        self.assertTrue({"fhs-netbox", "fhs-netbox-worker", "fhs-postgresql", "fhs-valkey-primary",
                         "fhs-grafana", "fhs-prometheus", "fhs-telegraf", "candidate-elastic", "candidate-elastic-kibana"} <= names)
        for obj in self.objects:
            if obj["kind"] == "PersistentVolumeClaim":
                self.assertEqual("keep", obj["metadata"]["annotations"]["helm.sh/resource-policy"])
                self.assertEqual("nfss1" if obj["metadata"]["name"] == "fhs-netbox-media" else "bds1", obj["spec"]["storageClassName"])
            if obj["kind"] == "StatefulSet":
                for claim in obj["spec"].get("volumeClaimTemplates", []):
                    self.assertEqual("bds1", claim["spec"]["storageClassName"])
                self.assertNotEqual("Delete", obj["spec"].get("persistentVolumeClaimRetentionPolicy", {}).get("whenDeleted"))

    def test_all_secret_references_have_keys_and_are_fresh(self):
        secrets = {o["metadata"]["name"]: o["data"] for o in self.objects if o["kind"] == "Secret"}
        self.assertEqual({"fhs-platform-credentials"}, set(secrets))
        def visit(value):
            if isinstance(value, dict):
                if "secretKeyRef" in value:
                    ref = value["secretKeyRef"]
                    self.assertIn(ref["key"], secrets[ref["name"]])
                if "secret" in value and isinstance(value["secret"], dict) and "items" in value["secret"]:
                    ref = value["secret"]
                    for item in ref["items"]:
                        self.assertIn(item["key"], secrets[ref.get("name", ref.get("secretName"))])
                for child in value.values(): visit(child)
            elif isinstance(value, list):
                for child in value: visit(child)
        visit(self.objects)
        data = secrets["fhs-platform-credentials"]
        for key in ["password", "db-password", "valkey-password", "admin-password", "elastic-password", "kibana-password"]:
            self.assertGreaterEqual(len(base64.b64decode(data[key])), 32)
        _, second = render()
        self.assertNotEqual(data["password"], next(o for o in second if o["kind"] == "Secret")["data"]["password"])

    def test_netbox_media_consumers_require_the_same_node(self):
        for release, namespace, worker_enabled, extra in (
            (RELEASE, NS, True, ()),
            ("another-release", "another-namespace", True,
             ("--set-string", "netbox.nameOverride=another-netbox")),
            (RELEASE, NS, False, ("--set", "netbox.worker.enabled=false")),
        ):
            with self.subTest(release=release, namespace=namespace, worker=worker_enabled):
                _, objects = render(extra=extra, release=release, namespace=namespace)
                claim = next(o for o in objects if o["kind"] == "PersistentVolumeClaim"
                             and o["metadata"]["name"] == "fhs-netbox-media")
                self.assertEqual(["ReadWriteOnce"], claim["spec"]["accessModes"])
                workloads = {o["metadata"]["name"]: (o, p) for o, p in pod_specs(objects)}
                web_labels = workloads["fhs-netbox"][0]["spec"]["template"]["metadata"]["labels"]
                expected_selector = {key: web_labels[key] for key in (
                    "app.kubernetes.io/name", "app.kubernetes.io/instance")}
                self.assertEqual(release, expected_selector["app.kubernetes.io/instance"])
                consumers = ["fhs-netbox", "fhs-netbox-housekeeping"]
                if worker_enabled:
                    consumers.append("fhs-netbox-worker")
                else:
                    self.assertNotIn("fhs-netbox-worker", workloads)
                for name in consumers:
                    with self.subTest(consumer=name):
                        obj, pod = workloads[name]
                        metadata = (obj["spec"]["jobTemplate"]["spec"]["template"]["metadata"]
                                    if obj["kind"] == "CronJob" else obj["spec"]["template"]["metadata"])
                        labels = metadata["labels"]
                        self.assertEqual(expected_selector, {key: labels[key] for key in expected_selector})
                        self.assertIn(labels["app.kubernetes.io/component"], ["netbox", "worker", "housekeeping"])
                        media = next(v for v in pod["volumes"] if v["name"] == "media")
                        self.assertEqual("fhs-netbox-media", media["persistentVolumeClaim"]["claimName"])
                        mount = next(m for m in pod["containers"][0]["volumeMounts"] if m["name"] == "media")
                        self.assertEqual("/opt/netbox/netbox/media", mount["mountPath"])
                        self.assertFalse(pod.get("nodeName"), name)
                        self.assertFalse(pod.get("nodeSelector"), name)
                        terms = pod.get("affinity", {}).get("podAffinity", {}).get(
                            "requiredDuringSchedulingIgnoredDuringExecution", [])
                        self.assertEqual(1, len(terms), name)
                        term = terms[0]
                        self.assertEqual("kubernetes.io/hostname", term["topologyKey"])
                        selector = term["labelSelector"]
                        self.assertEqual(expected_selector, selector["matchLabels"])
                        self.assertEqual([{"key": "app.kubernetes.io/component", "operator": "In",
                                           "values": ["netbox", "worker", "housekeeping"]}],
                                         selector["matchExpressions"])
                        self.assertEqual([namespace], term.get("namespaces", [namespace]))
                        self.assertNotIn("namespaceSelector", term)
                test_pod = next(o for o in objects if o["kind"] == "Pod"
                                and o["metadata"].get("annotations", {}).get("helm.sh/hook") == "test")
                self.assertNotIn("app.kubernetes.io/component", test_pod["metadata"]["labels"])
                for name, (_, pod) in workloads.items():
                    if name not in consumers:
                        affinity = pod.get("affinity") or {}
                        self.assertFalse((affinity.get("podAffinity") or {}).get(
                            "requiredDuringSchedulingIgnoredDuringExecution"), name)

    def test_shared_url_settings_nested_prefix_and_arbitrary_namespace(self):
        for raw_prefix in ("/test", "/review/team-a/", ""):
            prefix = raw_prefix.rstrip("/")
            text, objects = render(namespace="another-candidate", prefix=raw_prefix, hostname="example.invalid")
            self.check_safety(text, objects, "another-candidate", "example.invalid", prefix)
            config = next(o for o in objects if o["kind"] == "ConfigMap" and o["metadata"]["name"] == "fhs-netbox")
            netbox = yaml.safe_load(config["data"]["netbox.yaml"])
            netbox.update(yaml.safe_load(config["data"]["extra-0.yaml"]))
            self.assertEqual(f"{prefix}/netbox/".lstrip("/"), netbox["BASE_PATH"])
            self.assertEqual(["https://example.invalid"], netbox["CSRF_TRUSTED_ORIGINS"])
            self.assertEqual(f"{prefix}/netbox/", netbox["SESSION_COOKIE_PATH"])
            grafana = next(o for o in objects if o["kind"] == "ConfigMap" and o["metadata"]["name"] == "fhs-grafana")
            self.assertIn(f"root_url = https://example.invalid{prefix}/grafana/", grafana["data"]["grafana.ini"])
            self.assertIn("serve_from_sub_path = true", grafana["data"]["grafana.ini"])
            for obj, pod in pod_specs(objects):
                if obj["metadata"]["name"] == "fhs-netbox":
                    c = pod["containers"][0]
                    for probe in ("readinessProbe", "startupProbe"):
                        self.assertEqual(f"{prefix}/netbox/login/", c[probe]["httpGet"]["path"])
                if obj["metadata"]["name"] == "candidate-elastic-kibana":
                    c = pod["containers"][0]
                    env = {e["name"]:e.get("value") for e in c["env"]}
                    self.assertEqual(f"{prefix}/mid-cbf-kibana", env["SERVER_BASEPATH"])
                    self.assertEqual(f"https://example.invalid{prefix}/mid-cbf-kibana", env["SERVER_PUBLICBASEURL"])
                    self.assertEqual(f"{prefix}/mid-cbf-kibana/api/status", c["readinessProbe"]["httpGet"]["path"])
                if obj["metadata"]["name"] == "fhs-grafana":
                    c = pod["containers"][0]
                    env = {e["name"]:e.get("value") for e in c["env"]}
                    self.assertEqual(f"{prefix}/grafana/api/health", env["FHS_GRAFANA_HEALTH_PATH"])
                    self.assertNotIn("httpGet", c["readinessProbe"])

    def test_dashboard_unpack_script_runs_and_six_json_remain_selfcontained(self):
        text, objects = render(prefix="/review/team-a")
        cm = next(o for o in objects if o["metadata"]["name"] == "fhs-dashboard-archives")
        self.assertLess(sum(len(base64.b64decode(v)) for v in cm["binaryData"].values()), 1024*1024)
        pod = next(p for o, p in pod_specs(objects) if o["metadata"]["name"] == "fhs-grafana")
        script = next(c for c in pod["initContainers"] if c["name"] == "unpack-dashboards")["args"][0]
        with tempfile.TemporaryDirectory() as tmp:
            archives, dashboards = Path(tmp)/"archives", Path(tmp)/"dashboards"
            archives.mkdir(); dashboards.mkdir()
            for name, data in cm["binaryData"].items(): (archives/name).write_bytes(base64.b64decode(data))
            script = script.replace("/archives/", str(archives)+"/").replace("/dashboards/", str(dashboards)+"/")
            subprocess.run(["/bin/sh", "-ec", script], check=True, capture_output=True, text=True)
            self.assertEqual({f"{name}.json" for name in ["rack","mesh","fhs","switch","interface","vlan"]}, {p.name for p in dashboards.iterdir()})
            for p in dashboards.iterdir():
                actual = p.read_text()
                expected = gzip.decompress((archives/(p.name+".gz")).read_bytes()).decode().replace("/d/", "/review/team-a/grafana/d/")
                self.assertEqual(expected, actual)
                model = json.loads(actual)
                self.assertTrue(model["panels"])
                self.assertNotIn('"url": "/d/', actual)
                self.assertNotIn('"libraryPanel"', actual)
            self.assertIn("/var/lib/grafana/fhs-dashboards", json.dumps(next(o for o in objects if o["metadata"]["name"] == "fhs-grafana" and o["kind"] == "ConfigMap")))

    def test_netbox_launcher_serves_static_at_the_configured_base_path(self):
        for raw_prefix in ("/mid-cbf-hw", "/test", "/review/team-a", "/review/team-a/", ""):
            with self.subTest(prefix=raw_prefix):
                _, objects = render(prefix=raw_prefix)
                pod = next(p for o, p in pod_specs(objects) if o["metadata"]["name"] == "fhs-netbox")
                container = pod["containers"][0]
                self.assertEqual("fhs/netbox-inventory:4.7.0-2.7.1", container["image"])
                recipe=(CHART / "netbox-image/Dockerfile").read_text()
                self.assertIn("FROM ghcr.io/netbox-community/netbox@sha256:fa7ffa268c39fb258bed80bd256360a525f1a129ee4ee06298f10d6708578eba",recipe)
                self.assertNotIn("launch-netbox.sh",recipe,
                    "Refresh launcher fixture/provenance if the image recipe changes it")
                launched = netbox_launch(container)
                args = launched["args"]
                expected = raw_prefix.rstrip("/") + "/netbox/static"
                self.assertEqual(1, sum(a == "--static-path-route" or a.startswith("--static-path-route=") for a in args))
                self.assertEqual(expected, last_option(args, "--static-path-route"))
                self.assertEqual("/opt/netbox/netbox/static/", last_option(args, "--static-path-mount"))
                self.assertEqual("0.0.0.0", last_option(args, "--host"))
                self.assertEqual("8080", launched["port"])
                self.assertEqual("2", launched["workers"])
                self.assertEqual("wsgi", last_option(args, "--interface"))
                self.assertEqual("netbox.granian:application", args[-1])

    def test_external_database_preserves_separate_valkey(self):
        extra = ["--set", "postgresql.enabled=false", "--set-string", "netbox.externalDatabase.host=postgresql.old-monitoring.svc.cluster.local",
                 "--set-string", "netbox.externalDatabase.database=netbox_candidate_copy", "--set-string", "netbox.externalDatabase.username=netbox_candidate",
                 "--set-string", "netbox.externalDatabase.existingSecretName=candidate-db"]
        text, objects = render(extra=extra)
        self.check_safety(text, objects, NS, HOST, "/test")
        self.assertFalse(any(o["metadata"]["name"] == "fhs-postgresql" for o in objects))
        cm = next(o for o in objects if o["kind"] == "ConfigMap" and o["metadata"]["name"] == "fhs-netbox")
        cfg = yaml.safe_load(cm["data"]["netbox.yaml"])
        self.assertEqual("netbox_candidate_copy", cfg["DATABASES"]["default"]["NAME"])
        self.assertEqual("fhs-valkey-primary", cfg["REDIS"]["tasks"]["HOST"])
        self.assertEqual(0, cfg["REDIS"]["tasks"]["DATABASE"])
        self.assertEqual(1, cfg["REDIS"]["caching"]["DATABASE"])

    def test_invalid_inputs_rejected_before_any_apply(self):
        for prefix in ["/", "test", "//test", "/a//b", "/../test", "/test?foo", "/test#", "/a;cmd"]:
            with self.assertRaises(AssertionError): render(prefix=prefix)
        for ns in ("default", "kube-system", "mid-cbf-monitoring"):
            with self.assertRaises(AssertionError): render(namespace=ns)
        with self.assertRaises(AssertionError): render(extra=["--set", "postgresql.enabled=false"])
        with self.assertRaises(AssertionError): render(extra=["--is-upgrade"])

    def test_operator_managed_secret_and_portable_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp)/"fhs-platform"
            shutil.copytree(CHART, copied)
            text, objects = render(chart=copied, extra=["--set", "credentials.create=false"])
            self.assertFalse(any(o["kind"] == "Secret" for o in objects))
            self.check_safety(text, objects, NS, HOST, "/test")
            result = subprocess.run(["helm", "dependency", "list", str(copied)], capture_output=True, text=True, check=True)
            self.assertNotIn("missing", result.stdout)
            self.assertNotIn("wrong version", result.stdout)
        # Helm resolver.HashReq algorithm, cross-checked against upstream NetBox and Prometheus locks.
        req = yaml.safe_load((CHART/"Chart.yaml").read_text())["dependencies"]
        lock = yaml.safe_load((CHART/"Chart.lock").read_text())
        fields = ["name", "version", "repository", "condition", "tags", "enabled", "import-values", "alias"]
        req = [{k:x[k] for k in fields if k in x} for x in req]
        locked = [{k:x[k] for k in fields if k in x} for x in lock["dependencies"]]
        digest = "sha256:" + hashlib.sha256(json.dumps([req, locked], separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(lock["digest"], digest)

    def test_helm_server_lookup_preserves_every_credential_and_rejects_missing_key(self):
        old = copy.deepcopy(next(o for o in self.objects if o["kind"] == "Secret"))
        old["apiVersion"] = "v1"
        requests = []
        class API(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                requests.append(("GET", self.path))
                path = self.path.split("?")[0]
                if path == "/version": data = {"major":"1","minor":"31","gitVersion":"v1.31.0"}
                elif path == "/api": data = {"kind":"APIVersions","apiVersion":"v1","versions":["v1"],"serverAddressByClientCIDRs":[]}
                elif path == "/apis": data = {"kind":"APIGroupList","apiVersion":"v1","groups":[]}
                elif path == "/api/v1": data = {"kind":"APIResourceList","apiVersion":"v1","groupVersion":"v1","resources":[{"name":"secrets","singularName":"secret","namespaced":True,"kind":"Secret","verbs":["get","list"]}]}
                elif path == f"/api/v1/namespaces/{NS}/secrets/fhs-platform-credentials": data = old
                else:
                    self.send_response(404); self.end_headers(); return
                body = json.dumps(data).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        server = ThreadingHTTPServer(("127.0.0.1", 0), API)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config = Path(tmp)/"kubeconfig"
                config.write_text(yaml.safe_dump({"apiVersion":"v1","kind":"Config","clusters":[{"name":"mock","cluster":{"server":f"http://127.0.0.1:{server.server_port}"}}],"contexts":[{"name":"mock","context":{"cluster":"mock","user":"mock"}}],"current-context":"mock","users":[{"name":"mock","user":{}}]}))
                extra=["--is-upgrade", "--dry-run=server", "--kubeconfig", str(config), "--kube-context", "mock"]
                _, objects = render(extra=extra)
                new = next(o for o in objects if o["kind"] == "Secret")
                self.assertEqual(old["data"], new["data"])
                self.assertIn(("GET", f"/api/v1/namespaces/{NS}/secrets/fhs-platform-credentials"), requests)
                del old["data"]["secret_key"]
                with self.assertRaisesRegex(AssertionError, "missing key secret_key"):
                    render(extra=extra)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
