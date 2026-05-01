## Agent Sandboxes (Coding Agents in VMs)

Slicer can provision a fresh microVM, sync your workspace into it, and optionally launch a coding agent in one command.

```bash
slicer workspace [./path]       # Plain workspace + interactive shell (no agent)
slicer amp [./path]             # Amp sandbox
slicer claude [./path]          # Claude Code sandbox
slicer codex [./path]           # Codex sandbox
slicer opencode [./path]        # OpenCode sandbox
slicer copilot [./path]         # GitHub Copilot CLI sandbox
```

How they behave (based on the CLI help text):
- If the argument is a **local directory** (or omitted, defaulting to `.`), Slicer will create a new VM, wait for the guest agent, and copy your workspace into the VM.
- If the argument is **not** a local path, it is treated as a **VM name** and Slicer will reattach to that existing VM.

What each command does:
- **`slicer workspace`**: syncs your project into a clean VM and opens a shell. No coding agent is installed/launched.
- **`slicer amp/claude/codex/opencode/copilot`**: syncs your project, copies that tool's auth/config files into the VM, installs the agent via `arkade`, then attaches you to an agent session.

Reattach to an existing VM by name: `slicer amp amp-1`

Session modes (for the agent sandboxes): `--tmux none`, `--tmux local`, `--tmux remote`.
Default differs per command; check `slicer <agent> --help` if you need to be exact for the user's setup.

Use `.slicerignore` at workspace root to exclude files (same syntax as `.gitignore`).

---

## Common Workflows

### Run E2E tests in isolation

```bash
WORKFLOW=e2e-$(date +%Y%m%d-%H%M%S)
VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm cp ./project/ "$VM_NAME":/home/ubuntu/project/ --uid 1000
slicer vm exec "$VM_NAME" --uid 1000 --cwd ~/project -- "npm install && npm test"
slicer vm cp "$VM_NAME":/home/ubuntu/project/test-results/ ./results/
slicer vm delete "$VM_NAME"
```

### Remote Docker from macOS

```bash
# Forward Docker socket
slicer vm forward VM_NAME -L /tmp/docker.sock:/var/run/docker.sock &
export DOCKER_HOST=unix:///tmp/docker.sock

# Use Docker normally — containers run in the VM
docker build -t myapp .
docker run -d -p 8080:8080 myapp
```

### Build Go/Rust on Linux from macOS

```bash
WORKFLOW=build-$(date +%Y%m%d-%H%M%S)
VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm cp ./myproject/ "$VM_NAME":/home/ubuntu/myproject/ --uid 1000
slicer vm exec "$VM_NAME" --uid 1000 --cwd ~/myproject -- "make build"
slicer vm cp "$VM_NAME":/home/ubuntu/myproject/bin/app ./bin/app-linux
slicer vm delete "$VM_NAME"
```

### Quick k3s cluster

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

### Database testing

```bash
slicer vm exec VM_NAME --uid 1000 -- "sudo apt update && sudo apt install -y postgresql"
slicer vm forward VM_NAME -L 5432:127.0.0.1:5432 &
psql -h 127.0.0.1 -U postgres
```

### SSH/SCP access

```bash
slicer vm forward VM_NAME -L 2222:127.0.0.1:22 &
ssh -p 2222 ubuntu@127.0.0.1 uptime
scp -P 2222 ./file.txt ubuntu@127.0.0.1:/tmp/
```

Use SSH/SCP only if the task explicitly requires them (e.g., external scripts that only accept SSH). Otherwise, prefer `slicer vm exec` and `slicer vm cp`.

---

## Slicer on macOS (slicer-mac)

Slicer-mac runs a single Linux VM on Apple Silicon or Intel Macs, giving you a persistent Linux twin.

- **Socket**: `~/slicer-mac/slicer.sock` — auto-detected, no `--url` needed
- **Auth**: disabled by default for the local socket — no `--token` needed
- **Host groups**:
  - `slicer` — the persistent VM, like a Linux twin that survives reboots
  - `sbox` — ephemeral host group for API-launched sandbox VMs
- **Networking**: VMs cannot talk to each other, but can talk to the macOS host
- **Install**: `slicer install slicer-mac ~/slicer-mac`

```bash
# On macOS — just works, no flags
slicer vm list
VM_NAME=$(slicer vm add sbox --tag "workflow=smoke" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" --uid 1000 -- "uname -a"

# Launch an ephemeral sandbox
VM_NAME=$(slicer vm add sbox | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" --uid 1000 -- "make test"
slicer vm delete "$VM_NAME"
```

---

## Generating Config (Self-Hosted Linux)

Generate a YAML config to run your own Slicer daemon:

```bash
slicer new HOSTGROUP > config.yaml
```

Key flags for `slicer new`:

| Flag | Purpose |
|------|---------|
| `--count N` | Number of VMs to pre-launch (0 for API-only) |
| `--cpu N` | vCPUs per VM (default 2) |
| `--ram N` | RAM in GiB (default 4) |
| `--net isolated` | Isolated networking (no inter-VM traffic) |
| `--cidr 192.168.137.0/24` | Network range |
| `--api-bind 127.0.0.1` | TCP bind address |
| `--api-bind /tmp/slicer.sock` | Unix socket |
| `--api-auth=false` | Disable auth |
| `--image ghcr.io/...` | Custom rootfs image |
| `--storage image` | Persistent disk mode (default) |
| `--storage-size 25G` | Disk size |
| `--ssh-key "ssh-ed25519 ..."` | Inject SSH key |
| `--import-user USERNAME` | Import SSH keys from GitHub |
| `--userdata-file ./setup.sh` | Userdata script |
| `--graceful-shutdown=false` | Fast teardown |
| `--min` | Minimal image (faster boot, no Docker/K8s) |

### ⚠️ Avoid CIDR and host group conflicts

On Linux, multiple Slicer daemons can run simultaneously. **CIDRs and host group names must not overlap** across daemons — conflicts cause networking failures.

Before picking a CIDR range, check what's already in use:

```bash
# Check existing bridges and routes
ip addr show | grep -E "slicer|192\.168\.(137|138|139)"
ip route | grep 192.168

# Check for running slicer/firecracker processes
ps aux | grep -E "slicer|firecracker" | grep -v grep
```

Use distinct CIDRs per daemon (e.g. `192.168.137.0/24`, `192.168.138.0/24`, etc.) and unique host group names.

Start the daemon:

```bash
sudo -E slicer up ./config.yaml
```

---

## Custom Images

The default images are:
- `ghcr.io/openfaasltd/slicer-systemd:5.10.240-x86_64-latest` (full, with Docker/K8s kernel support)
- `ghcr.io/openfaasltd/slicer-systemd-min:6.1.90-x86_64-latest` (minimal, faster boot)
- `ghcr.io/openfaasltd/slicer-systemd-arm64:6.1.90-aarch64-latest` (ARM64)

### Building a custom image

1. Launch a VM with the default image
2. Customise it (install packages, configure services, etc.)
3. Export the disk to a new OCI image
4. Use the custom image in your config

```bash
# 1. Start a VM, customise it
VM_NAME=$(slicer vm add demo | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" --uid 1000 -- "sudo apt update && sudo apt install -y docker.io nginx golang"

# 2. Export the disk
slicer disk export "$VM_NAME" --output my-custom-image.img

# 3. Use it in config
slicer new mygroup --image ghcr.io/myorg/my-custom-image:latest > config.yaml
# Or set the image: field in existing YAML
```

In YAML config, set the `image:` field under a host group:

```yaml
config:
  host_groups:
    - name: mygroup
      image: ghcr.io/myorg/my-custom-image:latest
```

### Userdata (cloud-init style bootstrap)

Slicer supports userdata scripts — shell scripts that run once on first boot (similar to cloud-init). The script runs as root and is guarded by `/etc/slicer/userdata-ran` so it only executes once per disk.

Guideline: keep `userdata` strictly non-interactive and non-blocking.
- Scope: package install, user setup, and system configuration only.
- Avoid any long-running or interactive commands.
- Never use `kubectl port-forward`, `slicer vm forward`, background process launch, or shell interactivity in `userdata`.

```bash
# Inline
slicer vm add demo --userdata '#!/bin/bash
apt-get update && apt-get install -y docker.io
systemctl enable docker'

# From file
slicer vm add demo --userdata-file ./setup.sh

# In slicer new
slicer new demo --userdata-file ./setup.sh > config.yaml
```

Wait for userdata to finish before running commands:

```bash
slicer vm ready demo-1 --userdata --timeout 5m
```

---

## Secrets Management

```bash
slicer secret create --name my-secret --value "s3cret"
slicer secret list
slicer secret update --name my-secret --value "new-value"
slicer secret remove --name my-secret
```

VMs access secrets via `--secrets` on `slicer vm add`.

---

## Images & Disks

```bash
slicer image list              # List cached images
slicer image remove IMAGE      # Remove an image
slicer image wipe              # Remove all images

slicer disk list               # List disk leases
slicer disk export VM_NAME     # Export VM filesystem
slicer disk archive ...        # Archive sparse images
slicer disk sparsify ...       # Reclaim space
slicer disk transfer ...       # Compress + transfer via lz4
```

---

## Utility Commands

```bash
slicer info             # Client + server version
slicer version          # Client version only
slicer vm route ./cfg.yaml   # Show routing commands (for remote access from Mac/Linux)
slicer install TOOL     # Install additional tools via OCI
slicer update           # Replace binary with latest version
slicer activate         # Legacy command for GitHub Sponsors and for trial users only. Most users should get a license key from their email and save it to ~/.slicer/LICENSE
```

---

## Important Notes

1. **Default user**: uid auto-detected (ubuntu/1000). Use `--uid 1000` to be explicit. On non-Ubuntu images, the user is `slicer`
2. **First boot pulls image**: may take 30–60s on first run; subsequent boots are 1–3s.
3. **Port forwards block**: run them in background with `&`.
4. **Internet access**: VMs have outbound internet by default (bridge mode).
5. **Storage modes**: `image` (persistent, default), `devmapper`, `zfs`.
6. **Userdata runs once**: guarded by `/etc/slicer/userdata-ran` in the guest. Delete `.img` + `.lock` files to reset.
7. **.slicerignore**: place at workspace root to skip files during `slicer workspace/amp/claude/codex` copies.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Connection refused | Slicer daemon not running — start with `sudo -E slicer up config.yaml` |
| Permission denied | Use `sudo` for unix socket access, or verify `--token-file`/`--token` and local TCP credentials |
| VM not responding | `slicer vm ready VM_NAME --timeout 60s` |
| Command hangs | Long-running processes block `vm exec` — use `slicer vm bg exec` instead |
| Stale state | Delete `.img` and `.lock` files to reset persistent disks |
