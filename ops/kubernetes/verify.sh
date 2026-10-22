#!/usr/bin/env bash
# Disposable live checks; never uses the current kubeconfig context.
set -euo pipefail
profile=fhs-test
namespace="fhs-smoke-$(date +%s)-${RANDOM}"
k() { minikube -p "$profile" kubectl -- --context="$profile" --request-timeout=30s "$@"; }
cleanup() {
  local status=$?
  trap - EXIT
  if (( status != 0 )); then
    k -n "$namespace" get pods,pvc,events || true
    k -n "$namespace" logs client || true
    k -n "$namespace" logs volume-write || true
    k -n "$namespace" logs volume-read || true
  fi
  if ! k delete namespace "$namespace" --wait=true --timeout=90s; then
    echo "Cleanup incomplete: inspect namespace $namespace in context $profile" >&2
    status=1
  fi
  exit "$status"
}
k wait --for=condition=Ready nodes --all --timeout=180s
k -n kube-system wait --for=condition=Ready pods --all --timeout=180s
# Install cleanup only after this invocation successfully creates its namespace.
k create namespace "$namespace"
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
k -n "$namespace" apply -f - <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: web
  labels:
    app: fhs-smoke-web
spec:
  containers:
    - name: web
      image: busybox:1.37.0
      command: [sh, -ec, 'mkdir -p /www; echo fhs-network-ok > /www/index.html; exec httpd -f -p 8080 -h /www']
      ports:
        - containerPort: 8080
      readinessProbe:
        tcpSocket:
          port: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: fhs-smoke-web
  ports:
    - port: 8080
      targetPort: 8080
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: smoke
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 16Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: volume-write
spec:
  restartPolicy: Never
  containers:
    - name: writer
      image: busybox:1.37.0
      command: [sh, -ec, 'echo fhs-storage-ok > /data/probe; sync']
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: smoke
YAML
k -n "$namespace" wait --for=condition=Ready pod/web --timeout=180s
k -n "$namespace" run client --image=busybox:1.37.0 --restart=Never --command -- \
  sh -ec 'nslookup kubernetes.default.svc.cluster.local.; nslookup "$1"; wget -q -T 15 -O - "http://$1:8080" | grep -qx fhs-network-ok' \
  sh "web.$namespace.svc.cluster.local."
k -n "$namespace" wait --for=jsonpath='{.status.phase}'=Succeeded pod/client --timeout=180s
k -n "$namespace" wait --for=jsonpath='{.status.phase}'=Succeeded pod/volume-write --timeout=180s
# A second pod must read the persisted value after the writer is removed.
k -n "$namespace" delete pod volume-write --wait=true --timeout=60s
k -n "$namespace" run volume-read --image=busybox:1.37.0 --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"volume-read","image":"busybox:1.37.0","command":["sh","-ec","grep -qx fhs-storage-ok /data/probe"],"volumeMounts":[{"name":"data","mountPath":"/data"}]}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"smoke"}}]}}'
k -n "$namespace" wait --for=jsonpath='{.status.phase}'=Succeeded pod/volume-read --timeout=180s
k -n "$namespace" logs client
echo 'PASS: nodes, system pods, DNS, pod-to-service traffic, and PVC write/read'
