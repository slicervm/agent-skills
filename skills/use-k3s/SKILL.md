---
name: use-k3s
description: Install and verify a single-node K3s cluster on a local/Slicer VM with k3sup — no traefik, svclb LoadBalancer, kubeconfig merged into ~/.kube/config, nginx smoke test via 127.0.0.1. Use when asked to install k3s locally, get a working kubectl, or prove a cluster serves traffic.
allowed-tools: Bash
---

# Use K3s — single-node local cluster with a working LoadBalancer

Verified end-to-end on a Slicer VM (Ubuntu 22.04, k3s v1.36.3+k3s1,
k3sup 0.13.12, 2026-08-15). This is the in-VM, single-node, no-ingress flow:
kubectl works out of the box, no traefik, and a bare nginx pod is exposed as
a LoadBalancer reachable at 127.0.0.1. For remote/HA flows (k3sup over SSH,
k3sup-pro), see the `use-k3sup` skill instead.

## Golden rules

- Install tools with `arkade` in **one call** — `arkade get k3sup kubectl`
  (multiple tools download in parallel). Do NOT chain `arkade get k3sup &&
  arkade get kubectl`; that serialises the downloads. On Slicer VMs arkade
  is preinstalled; binaries land in `~/.arkade/bin` (ensure it is on PATH).
  See the `use-slicer` skill's `arkade.md` reference for the full pattern.
- Disable **only** traefik: `--k3s-extra-args '--disable traefik'`. Do NOT
  use `--no-extras` — it disables **both** traefik and servicelb (svclb), and
  svclb is what makes `--type=LoadBalancer` work.
- Merge the kubeconfig into `~/.kube/config` with `k3sup get-config --local
  --merge` so `kubectl` works with no `KUBECONFIG` export.
- Verify with `k3sup ready` (it exists for a reason — it polls until the
  control plane and default service account are actually usable), then
  `kubectl get nodes`.
- Trust nothing self-reported: prove the cluster serves traffic with the
  nginx LoadBalancer curl at the end.
- **Wait by polling readiness, not by blind `sleep`.** A fixed `sleep 8`
  (or a long inline sleep) is dead time — and in a recording it reads as the
  agent "stuck". Poll at 1s and break the instant the pod/svc is ready
  (see the smoke test below). Same idea as `k3sup ready`: check, don't guess.

## The verified sequence

```bash
# 1. Tools (arkade is preinstalled on Slicer VMs) — one call, parallel
export PATH=$PATH:~/.arkade/bin
arkade get k3sup kubectl

# 2. Install single-node K3s, no traefik, svclb kept
k3sup install --local --k3s-extra-args '--disable traefik'

# 3. Kubeconfig: merge into ~/.kube/config (kubectl works out of the box)
mkdir -p ~/.kube
k3sup get-config --local --merge --local-path ~/.kube/config

# 4. Wait for the cluster to be actually ready
k3sup ready

# 5. Verify
kubectl get nodes -o wide        # e2e-N  Ready  control-plane
kubectl get pods -A              # coredns, local-path-provisioner, metrics-server
                                 # (no traefik pods; svclb pod appears on first LB svc)
```

Notes from the run:

- `k3sup install --local` also drops a kubeconfig at `~/kubeconfig` by
  default — convenient, but not where kubectl looks. The `--merge`
  get-config step is what makes kubectl work without env vars. `--merge`
  merges with an existing kubeconfig at `--local-path` instead of
  clobbering it.
- The svclb DaemonSet (`svclb-<svc>`) is created **on demand** — it does not
  exist until the first LoadBalancer service is created. An empty
  `kubectl get pods -n kube-system | grep svclb` right after install is
  normal.
- `k3sup ready` polls the default service account (25 attempts) and returns
  when the API server is genuinely usable.

## Prove it serves traffic (nginx LoadBalancer smoke test)

```bash
kubectl run nginx-1 --image=nginx --port=80 --restart=Always
kubectl expose pod/nginx-1 --port=80 --type=LoadBalancer

# Wait for the svclb pod by polling readiness — do NOT blind-sleep.
# A fixed `sleep 8` (or worse, a long inline sleep) is dead time; poll at
# 1s and break the moment the pod is 1/1 Running (usually 2-4s, bounded 20s).
for i in $(seq 1 20); do
  kubectl get pods -n kube-system | grep -q 'svclb-nginx-1.*1/1.*Running' && break
  sleep 1
done
kubectl get svc nginx-1     # EXTERNAL-IP = node IP, PORT(S) 80:<nodeport>/TCP
kubectl get pods -n kube-system | grep svclb   # svclb-nginx-1-... 1/1 Running

# svclb listens on the node IP AND loopback — 127.0.0.1 works from the node:
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:80/   # 200
curl -s http://127.0.0.1:80/ | head -3                          # nginx welcome HTML
```

The LoadBalancer EXTERNAL-IP is the node's own IP (e.g. 172.16.0.2 on a
Slicer bridge VM); svclb binds all interfaces including loopback, so
`http://127.0.0.1:80/` is the simplest proof from inside the VM.

## Cleanup (when the VM is disposable)

```bash
kubectl delete pod nginx-1
k3s-killall.sh        # or: k3sup uninstall (remote form) / k3s-uninstall.sh
```

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `kubectl: command not found` after install | `arkade get kubectl`; ensure `~/.arkade/bin` on PATH |
| `kubectl: The connection to the server ... was refused` | kubeconfig not in `~/.kube/config` — rerun step 3; or `export KUBECONFIG=~/kubeconfig` |
| No LoadBalancer IP on the service | svclb disabled — check you used `--disable traefik`, not `--no-extras`; check `k3s \| grep -i servicelb` |
| `curl 127.0.0.1:80` hangs | svclb pod not up yet — `kubectl get pods -n kube-system`; wait for 1/1 Running |
| traefik pods still present | `--k3s-extra-args` not applied — reinstall with the flag (uninstall first) |
