---
name: use-slicer
description: Use Slicer to launch Linux microVMs for sandboxed builds, E2E tests, Docker, CI, and isolated dev environments — works from macOS and Linux hosts
tools: [Bash]
---

# Use Slicer — Launch Linux MicroVMs

Slicer gives you instant Linux microVMs powered by Firecracker. Use it when you need:

- A real Linux environment (especially from macOS)
- Sandboxed builds, CI, or E2E tests
- Docker/container workflows with port forwarding
- Isolated environments for untrusted or destructive operations
- Kubernetes (k3s) clusters for testing
- GPU/PCI passthrough workloads (via cloud-hypervisor backend)

VMs boot in 1–3 seconds, have full systemd, internet access, and SSH pre-installed.

Docs: https://docs.slicervm.com
Go SDK: https://github.com/slicervm/sdk (`github.com/slicervm/sdk`)

---

## Prerequisites — You Need a Running Daemon

Slicer is **not a SaaS**. It requires a running daemon that manages VMs. There are several ways to get one:

### Option A: macOS — slicer-mac (already running)

If the user is on macOS with slicer-mac installed, the daemon is already running. No setup needed.

```bash
# Auto-detected — no flags required
slicer info
slicer vm list
```

Socket: `~/slicer-mac/slicer.sock`. Auth: off by default. See the [macOS section](#slicer-on-macos-slicer-mac) below.

### Option B: Slicer Box — hosted at box.slicervm.com

A managed Slicer instance included with Slicer Home Edition. Provides **1 persistent VM** (2 vCPU, 4GB RAM, 10GB disk) accessible over HTTPS.

```bash
export SLICER_URL=https://box.slicervm.com
export SLICER_TOKEN_FILE=~/.slicer/gh-access-token
```

The token file is a GitHub personal access token stored at `~/.slicer/gh-access-token`.

**Constraints:**
- 1 VM only (single host group, single VM)
- Persistent disk — data survives reboots
- Cannot create/delete multiple VMs; you get one and recycle it
- Fixed specs (2 vCPU, 4GB RAM, 10GB disk)

**Factory reset** — wipes the disk and starts fresh:

```bash
# Get VM name first
slicer vm list --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"

# Delete (all data lost) then re-launch
slicer vm delete VM_NAME --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
slicer vm launch --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
slicer vm ready VM_NAME --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE" --timeout 120s
```

Otherwise the VM keeps its state between sessions — installed packages, files, and services persist.

### Option C: Linux — connect to an existing Slicer instance

If Slicer is already running on the machine (or a LAN machine), connect to it. **Ask the user** for the URL and token path — don't guess.

```bash
# Local unix socket (no auth)
export SLICER_URL=/path/to/slicer.sock

# Local TCP
export SLICER_URL=http://127.0.0.1:8080
export SLICER_TOKEN_FILE=/var/lib/slicer/auth/token

# Remote machine on LAN
export SLICER_URL=https://192.168.1.50:8080
export SLICER_TOKEN_FILE=/path/to/token
```

Check for a running daemon:

```bash
ps aux | grep -E "slicer|firecracker" | grep -v grep
```

### Option D: Linux — start a new Slicer daemon

If no daemon is running, start one. **Check for conflicts first** — CIDRs and host group names must not overlap with any other running instance.

```bash
# Check for existing instances
ps aux | grep -E "slicer|firecracker" | grep -v grep
ip route | grep 192.168

# Generate config with a unique CIDR
slicer new sandbox --count=0 --graceful-shutdown=false \
  --api-bind=/tmp/slicer-sandbox.sock --api-auth=false \
  --cidr 192.168.140.0/24 > sandbox.yaml

# Start daemon
sudo -E slicer up ./sandbox.yaml > /tmp/slicer.log 2>&1 &
echo $! | sudo tee /run/slicer.pid

export SLICER_URL=/tmp/slicer-sandbox.sock
```

### Option E: Remote Linux machine over SSH

SSH into a remote/LAN machine, start Slicer there, then use the REST API remotely:

```bash
# On the remote machine (via SSH)
ssh user@192.168.1.50
slicer new sandbox --api-bind 0.0.0.0 --api-port 8080 > sandbox.yaml
sudo -E slicer up ./sandbox.yaml &

# Back on your local machine — use the remote API
export SLICER_URL=http://192.168.1.50:8080
export SLICER_TOKEN_FILE=./remote-token  # copy token from remote /var/lib/slicer/auth/token
slicer vm list --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```

### Verify connectivity

```bash
slicer info --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```

Every `slicer vm` subcommand accepts `--url` and `--token-file` (or `--token`).

---

## Working with VMs

### List VMs and host groups

```bash
slicer vm list --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
slicer vm group --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```

Use `--json` for machine-readable output.

### Create a VM

```bash
slicer vm add HOSTGROUP --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```

The hostname is printed on creation (e.g. `demo-3`). Key flags:

| Flag | Purpose |
|------|---------|
| `--cpus N` | Override vCPU count |
| `--ram-gb N` | Override RAM (also `--ram-mb`, `--ram-bytes`) |
| `--userdata '#!/bin/bash\n...'` | Bootstrap script |
| `--userdata-file ./setup.sh` | Bootstrap from file |
| `--ssh-key "ssh-ed25519 ..."` | Inject SSH public key |
| `--ready agent` | Block until agent is ready |
| `--ready userdata` | Block until userdata finishes |
| `--shell` | Open shell immediately after boot |
| `--tag env=ci` | Metadata tags |
| `--secrets secret1,secret2` | Allow access to named secrets |

### Wait for readiness

```bash
# Block until the slicer-agent is responsive (default)
slicer vm ready VM_NAME --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"

# Block until userdata script has finished
slicer vm ready VM_NAME --userdata --timeout 5m

# Block for both agent AND userdata
slicer vm ready VM_NAME --agent --userdata --timeout 5m
```

`--agent` waits for the in-VM slicer-agent (vsock RPC). `--userdata` waits for the bootstrap script to complete (guarded by `/etc/slicer/userdata-ran` in the guest). Polling interval: `--interval 100ms` (default).

### Non-blocking health check

```bash
slicer vm health VM_NAME --json    # Agent version, uptime, stats — does not block
```

---

## Running Commands

### Execute a command

```bash
slicer vm exec VM_NAME -- "whoami"
```

The default user is auto-detected (typically `ubuntu`, uid 1000). Override with `--uid`:

```bash
slicer vm exec VM_NAME --uid 1000 -- "sudo apt update && sudo apt install -y nginx"
```

Key flags:

| Flag | Purpose |
|------|---------|
| `--uid 1000` | Run as ubuntu user (passwordless sudo) |
| `--cwd ~/project` | Set working directory |
| `--env KEY=VALUE` | Pass environment variables (repeatable) |
| `--shell ""` | Skip shell interpreter, exec directly |

Pipes and stdin work:

```bash
# Pipe local file into VM
cat script.sh | slicer vm exec VM_NAME -- "bash"

# Pipes inside VM
slicer vm exec VM_NAME -- "ps aux | grep nginx"
```

### Interactive shell

```bash
slicer vm shell VM_NAME
```

Flags: `--uid`, `--cwd`, `--bootstrap "command"` (run on connect).

---

## File Transfer

### Copy files to/from VMs

```bash
# Single file (binary mode — the default when no --mode is given)
slicer vm cp ./local-file.txt VM_NAME:/tmp/file.txt --uid 1000

# Single file from VM
slicer vm cp VM_NAME:/etc/os-release ./os-release.txt

# Single file with custom permissions (binary mode)
slicer vm cp ./script.sh VM_NAME:/tmp/script.sh --mode=binary --permissions 0755 --uid 1000

# Whole directory — use --mode=tar
slicer vm cp ./my-project/ VM_NAME:/home/ubuntu/project/ --uid 1000 --mode=tar

# Directory with exclusions
slicer vm cp ./src/ VM_NAME:/home/ubuntu/src/ --uid 1000 --mode=tar \
  --exclude '**/.git/**' --exclude '**/node_modules/**'
```

Key flags:

| Flag | Purpose |
|------|---------|
| (no `--mode`) | Binary mode — single files only (default) |
| `--mode=tar` | Tar mode — required for copying directories |
| `--mode=binary --permissions 0755` | Binary mode with custom file permissions |
| `--uid 1000` | File ownership |
| `--exclude 'pattern'` | Glob exclude patterns (tar mode only, repeatable) |

---

## Port Forwarding

Forward ports from VMs to your local machine using `-L` (SSH-style syntax):

```bash
# TCP port forward
slicer vm forward VM_NAME -L 8080:127.0.0.1:8080

# Remap ports
slicer vm forward VM_NAME -L 3000:127.0.0.1:8080

# Unix socket → local TCP (e.g. Docker)
slicer vm forward VM_NAME -L 127.0.0.1:2375:/var/run/docker.sock

# Unix socket → local Unix socket
slicer vm forward VM_NAME -L /tmp/docker.sock:/var/run/docker.sock

# SSH access
slicer vm forward VM_NAME -L 2222:127.0.0.1:22

# Multiple forwards at once
slicer vm forward VM_NAME -L 8080:127.0.0.1:8080 -L 5432:127.0.0.1:5432
```

Port forwards run in the foreground — use `&` to background them.

See [references/networking.md](references/networking.md) for bridge vs isolated networking.

---

## VM Lifecycle

```bash
slicer vm pause VM_NAME       # Freeze (saves CPU, instant resume)
slicer vm resume VM_NAME      # Unfreeze
slicer vm shutdown VM_NAME    # Graceful shutdown
slicer vm delete VM_NAME      # Remove VM
slicer vm suspend VM_NAME     # Save state to disk (snapshot)
slicer vm restore VM_NAME     # Restore from snapshot
```

### Monitoring

```bash
slicer vm health VM_NAME      # Agent status, version, stats (--json)
slicer vm top                 # Live metrics for all VMs
slicer vm top VM_NAME         # Live metrics for one VM
slicer vm logs VM_NAME        # Boot/console log (--lines N)
```

---

## Agent Sandboxes (Coding Agents in VMs)

Launch coding agents (Amp, Claude Code, Codex) inside isolated VMs with one command:

```bash
slicer amp [./path]             # Amp sandbox
slicer claude [./path]          # Claude Code sandbox
slicer codex [./path]           # Codex sandbox
slicer workspace [./path]       # Plain workspace, no agent
```

These commands:
1. Create a fresh microVM
2. Copy credentials and workspace into the VM
3. Install the agent tool
4. Attach you to the session (via tmux or direct)

Reattach to an existing VM by name: `slicer amp amp-1`

Session modes: `--tmux local` (default), `--tmux remote`, `--tmux none`.

Use `.slicerignore` at workspace root to exclude files (same syntax as `.gitignore`).

---

## Common Workflows

### Run E2E tests in isolation

```bash
slicer vm add sandbox --ready agent
slicer vm cp ./project/ sandbox-1:/home/ubuntu/project/ --uid 1000
slicer vm exec sandbox-1 --uid 1000 --cwd ~/project -- "npm install && npm test"
slicer vm cp sandbox-1:/home/ubuntu/project/test-results/ ./results/
slicer vm delete sandbox-1
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
slicer vm add sandbox --ready agent
slicer vm cp ./myproject/ sandbox-1:/home/ubuntu/myproject/ --uid 1000
slicer vm exec sandbox-1 --uid 1000 --cwd ~/myproject -- "make build"
slicer vm cp sandbox-1:/home/ubuntu/myproject/bin/app ./bin/app-linux
slicer vm delete sandbox-1
```

### Quick k3s cluster

```bash
slicer vm exec VM_NAME --uid 1000 -- "curl -sfL https://get.k3s.io | sh -"
slicer vm ready VM_NAME --userdata --timeout 2m
slicer vm forward VM_NAME -L 6443:127.0.0.1:6443 &
slicer vm cp VM_NAME:/etc/rancher/k3s/k3s.yaml ./k3s.yaml
KUBECONFIG=./k3s.yaml kubectl get nodes
```

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
slicer vm exec slicer-1 --uid 1000 -- "uname -a"

# Launch an ephemeral sandbox
slicer vm add sbox
slicer vm ready sbox-1
slicer vm exec sbox-1 --uid 1000 -- "make test"
slicer vm delete sbox-1
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
| `--github USERNAME` | Import SSH keys from GitHub |
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
slicer vm add demo --ready agent
slicer vm exec demo-1 --uid 1000 -- "sudo apt update && sudo apt install -y docker.io nginx golang"

# 2. Export the disk
slicer disk export demo-1 --output my-custom-image.img

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
slicer vm route ./cfg   # Show routing commands (for remote access from Mac/Linux)
slicer install TOOL     # Install additional tools via OCI
slicer update           # Replace binary with latest version
slicer activate         # Activate Slicer Home Edition license
```

---

## Important Notes

1. **Default user**: uid auto-detected (ubuntu/1000). Use `--uid 1000` to be explicit.
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
| Permission denied | Use `sudo` for unix socket commands, or check `--token-file` for HTTP |
| VM not responding | `slicer vm ready VM_NAME --timeout 60s` |
| Command hangs | Background processes in exec can hang — use `nohup ... &` |
| Stale state | Delete `.img` and `.lock` files to reset persistent disks |
