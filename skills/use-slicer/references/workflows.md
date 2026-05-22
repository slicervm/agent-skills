# Common Workflows

Worked recipes that combine the core `slicer vm` commands. Copy-paste starting points — adapt host group names, paths, and ports to the task.

## Run E2E tests in isolation

```bash
WORKFLOW=e2e-$(date +%Y%m%d-%H%M%S)
VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm cp ./project/ "$VM_NAME":/home/ubuntu/project/ --uid 1000
slicer vm exec "$VM_NAME" --uid 1000 --cwd ~/project -- "npm install && npm test"
slicer vm cp "$VM_NAME":/home/ubuntu/project/test-results/ ./results/
slicer vm delete "$VM_NAME"
```

## Remote Docker from macOS

```bash
# Forward Docker socket
slicer vm forward VM_NAME -L /tmp/docker.sock:/var/run/docker.sock &
export DOCKER_HOST=unix:///tmp/docker.sock

# Use Docker normally — containers run in the VM
docker build -t myapp .
docker run -d -p 8080:8080 myapp
```

## Build Go/Rust on Linux from macOS

```bash
WORKFLOW=build-$(date +%Y%m%d-%H%M%S)
VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm cp ./myproject/ "$VM_NAME":/home/ubuntu/myproject/ --uid 1000
slicer vm exec "$VM_NAME" --uid 1000 --cwd ~/myproject -- "make build"
slicer vm cp "$VM_NAME":/home/ubuntu/myproject/bin/app ./bin/app-linux
slicer vm delete "$VM_NAME"
```

## Quick k3s cluster

```bash
WORKFLOW=k3s-$(date +%Y%m%d-%H%M%S)
VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
# Install Kubernetes CLIs with arkade (already available on slicer images).
# Default install path is ~/.arkade/bin.
slicer vm exec "$VM_NAME" --uid 1000 -- "arkade get k3sup kubectl helm"
slicer vm exec "$VM_NAME" --uid 1000 -- "curl -sfL https://get.k3s.io | sh -"
slicer vm ready "$VM_NAME" --userdata --timeout 2m
slicer vm forward "$VM_NAME" -L 6443:127.0.0.1:6443 &
slicer vm cp "$VM_NAME":/etc/rancher/k3s/k3s.yaml ./k3s.yaml
export PATH=$PATH:$HOME/.arkade/bin
KUBECONFIG=./k3s.yaml kubectl get nodes
```

For Kubernetes bootstrap workflows, prefer pulling toolchain CLIs via `arkade` (for example `arkade get k3sup kubectl` and `arkade get helm`) rather than external ad-hoc installers. Keep in mind the binaries are under `~/.arkade/bin`.

Do not start cluster accessibility flows (such as `kubectl port-forward`) inside `userdata`. Use `userdata` only for setup/bootstrap tasks, then use `slicer vm forward` from the host after VM readiness for host access.

Also avoid any blocking call inside `userdata`; keep it non-interactive and short-lived. Port-forwarding, shell sessions, and long-running daemons should be started after VM boot (use `slicer vm bg exec` for processes that need to survive client disconnect).

For more on `k3sup` provisioning, see the `use-k3sup` skill.

## Database testing

```bash
slicer vm exec VM_NAME --uid 1000 -- "sudo apt update && sudo apt install -y postgresql"
slicer vm forward VM_NAME -L 5432:127.0.0.1:5432 &
psql -h 127.0.0.1 -U postgres
```

## SSH/SCP access

```bash
slicer vm forward VM_NAME -L 2222:127.0.0.1:22 &
ssh -p 2222 ubuntu@127.0.0.1 uptime
scp -P 2222 ./file.txt ubuntu@127.0.0.1:/tmp/
```

Use SSH/SCP only if the task explicitly requires them (e.g., external scripts that only accept SSH). Otherwise, prefer `slicer vm exec` and `slicer vm cp`.
