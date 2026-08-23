---
name: install-openfaas-standard
description: Install OpenFaaS Standard (Pro) on a single-node k3s and prove a side-loaded Python function end-to-end via gateway invocations. Minimal known-good steps — no pod watching, no health probing, retries on actions only. Use when asked to install OpenFaaS on Kubernetes/k3s and deploy or iterate a function.
allowed-tools: Bash
---

# Install OpenFaaS Standard on k3s — minimal path

Every command below earns its place. Do not add steps, checks, waits, or
research. **Retries on actions, never barriers on state**: nothing here
watches pods or polls readiness — if an action can fail transiently, it is
retried until it succeeds, and the retried action doubles as the probe.

## 1. Tooling + cluster + docker (one screen)

```bash
arkade get k3sup kubectl faas-cli helm
export PATH=$PATH:$HOME/.arkade/bin
mkdir -p ~/.kube
k3sup install --local --local-path ~/.kube/config --k3s-extra-args '--disable traefik'
export KUBECONFIG=$HOME/.kube/config
sudo systemctl start docker
```

Do not wait for the node. The next commands go through the API server,
which k3sup has already confirmed.

## 2. OpenFaaS Standard via the Helm chart

Licence file is expected at `~/openfaas-license`. **The secret must contain
only the JWT.** Some licence files carry a comment block followed by a `---`
separator with the token after it — creating the secret from such a file
verbatim gives a gateway CrashLoopBackOff. If the file contains `---`, extract
what follows it first:

```bash
grep -q -- '---' ~/openfaas-license && sed -n '/^---$/,$p' ~/openfaas-license | tail -n +2 > ~/openfaas-license.jwt && mv ~/openfaas-license.jwt ~/openfaas-license
```

```bash
kubectl apply -f https://raw.githubusercontent.com/openfaas/faas-netes/master/namespaces.yml
kubectl create secret generic openfaas-license -n openfaas --from-file license=$HOME/openfaas-license
helm repo add openfaas https://openfaas.github.io/faas-netes
helm upgrade --install openfaas openfaas/openfaas -n openfaas \
  --set openfaasPro=true --set clusterRole=true \
  --set functions.imagePullPolicy=IfNotPresent
```

**Do not watch the rollout.** Go straight to the function build — the
cluster pulls images while you work. The gateway is a NodePort at
`http://127.0.0.1:31112` (chart default); no port-forward is needed.

Do not fetch the password or log in yet — that comes AFTER the build,
by which time the gateway is up and the login lands first try. Logging
in now means visibly retrying against a NodePort that refuses until the
gateway image has pulled.

## 3. Function: scaffold, bytes-safe handler, side-load, deploy

ttl.sh and public registries are not used — side-load into k3s's
containerd. In `python3-http`, `event.body` is **bytes**: decode it, or the
handler 500s. Use this handler verbatim and edit only the message string:

```bash
faas-cli new --lang python3-http myfn
cat > myfn/handler.py <<'EOF'
def handle(event, context):
    body = event.body.decode() if isinstance(event.body, bytes) else str(event.body)
    return {"statusCode": 200, "body": f"v1: hello. you said: {body}"}
EOF
sed -i 's|image: myfn:latest|image: myfn:v1|' stack.yaml
sg docker -c 'faas-cli build -f stack.yaml'
sg docker -c 'docker save myfn:v1' | sudo k3s ctr -n k8s.io images import -
for i in $(seq 1 30); do
  PW=$(kubectl get secret -n openfaas basic-auth -o jsonpath='{.data.basic-auth-password}' 2>/dev/null | base64 -d) && [ -n "$PW" ] && break
  sleep 2
done
echo "$PW" | faas-cli login -g http://127.0.0.1:31112 -u admin --password-stdin
faas-cli deploy -f stack.yaml -g http://127.0.0.1:31112
```

If the login or deploy is refused (gateway still starting), retry that
same command after 5s — it is the probe; add nothing else.

If `faas-cli deploy` fails because the gateway isn't answering yet, run the
same command again after 5s — the deploy is the probe. Do not check pods.

## 4. Prove it: retry the invocation, expect the marker

The invoke retried until its output contains the current version marker is
the ONLY verification in this skill. It absorbs scheduling, image import,
and rollout propagation in one loop with zero state-watching:

```bash
for i in $(seq 1 60); do
  OUT=$(curl -s -m 5 http://127.0.0.1:31112/function/myfn -d "ping" 2>/dev/null)
  echo "$OUT" | grep -q "v1:" && { echo "GATEWAY: $OUT"; break; }
  sleep 2
done
```

## 5. Iterate (repeat per version: v2, v3, …)

```bash
sed -i 's/v1: hello/v2: updated/' myfn/handler.py
sed -i 's|image: myfn:v1|image: myfn:v2|' stack.yaml
sg docker -c 'faas-cli build -f stack.yaml'
sg docker -c 'docker save myfn:v2' | sudo k3s ctr -n k8s.io images import -
faas-cli deploy -f stack.yaml -g http://127.0.0.1:31112
# same invoke loop, expecting "v2:" — the changed marker IS the rollout check
```

## What NOT to do (each of these cost a real run minutes)

- **No `/ping`** — the gateway has no such endpoint (404, always).
- **No unauthenticated `/system/*` probes** — they 401 regardless of health.
  If you must probe at all, `/healthz` is the only open endpoint; but the
  retried deploy/invoke already covers it.
- **No `kubectl get pods -w`, no `kubectl wait`, no rollout status, no
  Ready-condition loops** — in any namespace, for any component. One run
  burned 195s watching six components it never needed.
- **No docker storage-driver / daemon.json changes.** Side-loading works as
  is. `docker inspect` imageIDs won't match the pod's — that is cosmetic;
  do not investigate it.
- **No registry pushes, no ttl.sh.**
- **No reading chart values or docs** — every needed `--set` is above.
