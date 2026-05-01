---
name: use-slicer
description: Use Slicer to launch Linux microVMs for sandboxed builds, E2E tests, Docker, CI, and isolated dev environments — works from macOS and Linux hosts
license: MIT
compatibility: Requires Bash, the Slicer CLI, and access to a running Slicer daemon or slicer-mac.
---

# Use Slicer — Launch Linux MicroVMs

Slicer gives you instant Linux microVMs powered by Firecracker. Use it when you need:

- A real Linux environment with systemd, Internet access and SSH preinstalled(especially from macOS)
- Sandboxed builds, CI, or E2E tests
- Docker/container workflows with port forwarding
- Isolated environments for untrusted or destructive operations
- Kubernetes (k3s) clusters for testing
- GPU/PCI passthrough workloads (via cloud-hypervisor backend)
- Automated code review pipelines in ephemeral microVMs
- Running coding agents in isolated microVMs (Amp, Claude Code, Codex, OpenCode, GitHub Copilot CLI) then copying out the outcome - code, files, reports, binaries, images, etc.

VMs boot in 1–3 seconds, have full systemd, internet access, and SSH pre-installed.

Docs: https://docs.slicervm.com
Go SDK: https://github.com/slicervm/sdk (`github.com/slicervm/sdk`)

## Slicer for Mac

The Slicer CLI also works as a client for Slicer for Mac.

Slicer for Mac ships a persistent Linux VM named `slicer-1` that can be used for local development and testing, with a permanent disk - it's analogous to WSL2.

Slicer for Mac has 2x hostgroups which are fixed: `slicer` (may only launch 1x VM named `slicer-1`) and `sbox` (for ephemeral API-launched sandboxes).

Slicer for Mac's socket is auto-detected at `~/slicer-mac/slicer.sock` - no `--url` needed.

Slicer for Mac uses VMNet networking, which does not allow for inter-VM traffic, but does allow for host <> VM traffic. The host can access TCP ports on the VM directly by using its IP address shown on `slicer vm list`, or by using the `slicer vm forward` command which is similar to `ssh -L` or `kubectl port-forward` but for TCP traffic and UNIX sockets.

---

## Prerequisites — You Need a Running Daemon

Slicer is **not a SaaS**. It requires a running daemon that manages VMs. There are several ways to get one:

### Deterministic Workflow (Default)

For agent tasks that can create infrastructure, use this default pattern:

1. Reuse the session VM when already known (for example, because the same workflow tagged VM was created earlier in this run). Otherwise create a new VM and tag it.
2. Track and pass the session VM name forward (instead of switching to an arbitrary existing VM) so subsequent commands in the same session stay on the same instance.
3. Tag VMs so they are identifiable later, for example `workflow=<slug>`.
4. Run in-VM commands with native `slicer vm` operations (`exec`, `bg exec`, `cp`, `shell`).
   - Use `slicer vm exec` for short, atomic commands.
   - Use `slicer vm bg exec` for long-running processes (dev servers, builds) that should survive client disconnect — check back with `bg logs`, `bg wait`, and clean up with `bg kill` + `bg remove`.
   - Use `slicer vm shell` for long sessions or multiple related commands (interactive PTY).
5. Prefer native Slicer commands over SSH even when SSH is available.

Example:

```bash
WORKFLOW=ci-$(date +%Y%m%d-%H%M%S)
# Reuse SESSION_VM if already set for this run, else create once and record it.
if [ -n "${SLICER_SESSION_VM:-}" ]; then
  VM_NAME="$SLICER_SESSION_VM"
else
  VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
  slicer vm ready "$VM_NAME"
  export SLICER_SESSION_VM="$VM_NAME"
fi

# then use returned hostname in subsequent commands:
slicer vm exec "$VM_NAME" --uid 1000 -- "uname -a"
slicer vm cp ./local.txt "$VM_NAME":/tmp/local.txt --uid 1000
# for longer interactive work, open a shell session instead of repeating many one-off execs:
slicer vm shell "$VM_NAME" --uid 1000

# use exec for deterministic one-liners; use shell for ongoing interactive workflows
```

### Option A: macOS — slicer-mac (already running)

If the user is on macOS with slicer-mac installed, the daemon is already running. No setup needed.

```bash
# Auto-detected — no flags required
slicer info
slicer vm list
```

On slicer-mac, always launch API-created microVMs with explicit `sbox` host group:

```bash
slicer vm add sbox --tag workflow=<slug>
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
# Local unix socket (no auth; may require sudo/root to read the socket)
export SLICER_URL=/path/to/slicer.sock

# Local TCP
export SLICER_URL=http://127.0.0.1:8080
# Local API token may require sudo/root to read unless explicitly provided
export SLICER_TOKEN_FILE=/var/lib/slicer/auth/token

# Prefer explicit env vars when token file is not accessible:
export SLICER_TOKEN=$(sudo cat /var/lib/slicer/auth/token)
# or let user provide a token: export SLICER_TOKEN_FILE=...

# Remote machine on LAN
export SLICER_URL=https://192.168.1.50:8080
export SLICER_TOKEN_FILE=/path/to/token
```

Check for a running daemon:

```bash
ps aux | grep -E "slicer|firecracker" | grep -v grep
```

Notes:
- For a local TCP API (`http://127.0.0.1:8080`), read `/var/lib/slicer/auth/token` only with sufficient privileges (typically `sudo`).
- If the user provides `SLICER_TOKEN`/`SLICER_TOKEN_FILE`, use those values directly and avoid guessing defaults.
- If a specific remote endpoint is provided (for example, `192.168.1.25:8080`), use that URL as given and do not infer local token path behavior.

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

# Remote Linux slicer endpoints typically already have pre-created VMs.
# Prefer reusing existing VMs from `slicer vm list` rather than creating new ones
# with `slicer vm add`, unless the user explicitly asks to create a VM.
slicer vm list --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```

### Verify connectivity

```bash
slicer info --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```

Every `slicer vm` subcommand accepts `--url` and `--token-file` (or `--token`).

---

## CLI shortcuts you should surface

Slicer exposes a few **top-level shortcuts** for common VM operations (not for every `slicer vm ...` subcommand). Prefer showing these when they match what the user asked for:

- `slicer ls` is a shortcut for `slicer vm list` (and `slicer vm list` itself has aliases `ls`/`l`)
- `slicer shell` is a shortcut for `slicer vm shell`
- `slicer cp` is a shortcut for `slicer vm cp`
- `slicer bg` is a shortcut for `slicer vm bg` (so `slicer bg exec`, `slicer bg logs`, etc. all work)

The `slicer vm` command group itself also has aliases: `slicer vm` == `slicer v`.

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

The hostgroup argument is optional when only one host group is configured — the SDK resolves it automatically. When there are multiple host groups you must specify one explicitly.

If SSH access is needed, configure key material at launch time:
- for local keys: pass a real public key string via `--ssh-key`
- for GitHub key import: pass via `--import-user USERNAME`

Use `slicer vm add --help` first to verify current flag names and supported auth options before constructing the launch command.

```bash
slicer vm add --help
```

The hostname is printed on creation (e.g. `demo-3`). Key flags:

| Flag | Purpose |
|------|---------|
| `--cpus N` | Override vCPU count |
| `--ram-gb N` | Override RAM (also `--ram-mb`, `--ram-bytes`) |
| `--userdata '#!/bin/bash\n...'` | Bootstrap script |
| `--userdata-file ./setup.sh` | Bootstrap from file |
| `--ssh-key "ssh-ed25519 ..."` | Inject SSH public key |
| `--import-user USERNAME` | Import SSH keys from GitHub user |
| `--shell` | Open shell immediately after boot |
| `--tag env=ci` | Metadata tags |
| `--secrets secret1,secret2` | Allow access to named secrets |

Important: do not use readiness flags on `slicer vm add`. If startup blocking or readiness is required, run `slicer vm ready <VM_NAME>` as a separate step.

When creating VMs for mutable tasks, do not target or reuse `slicer-1` on slicer-mac unless the user explicitly requests it. Reuse the session's tagged VM when known; otherwise create a new VM with explicit `--tag`.

### Persistent temporary VMs

Use `--persistent` when you want a VM that survives daemon restarts and shutdowns but is still a disposable, tagged sandbox (not the primary twin). Always pair it with a descriptive `--tag` so the VM can be rediscovered later.

**On slicer-mac**: launch into the `sbox` host group explicitly — the `slicer` group is reserved for the persistent Linux twin.

```bash
VM_NAME=$(slicer vm add sbox --persistent \
  --tag "workflow=rustfs" --tag "purpose=s3-demo" \
  | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"

# Rediscover later by tag:
slicer vm list --json | jq -r '.[] | select(.tags.workflow=="rustfs") | .hostname'
```

**On Slicer for Linux**: host group names vary per deployment. Either:

1. List groups first and pick an appropriate one:
   ```bash
   slicer vm group --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
   slicer vm add <group> --persistent --tag "workflow=..." ...
   ```
2. Or skip the check and launch into the default group by omitting the positional arg:
   ```bash
   slicer vm add --persistent --tag "workflow=..." ...
   ```

### Wait for readiness

```bash
# Block until the slicer-agent is responsive (default)
slicer vm ready VM_NAME --agent --timeout 5m

# Block until userdata script has finished
slicer vm ready VM_NAME --userdata --timeout 5m
```

`--agent` waits for the in-VM slicer-agent (vsock RPC). `--userdata` waits for the bootstrap script to complete (guarded by `/etc/slicer/userdata-ran` in the guest). Polling interval: `--interval 100ms` (default).

Prefer `slicer vm shell` for interactive workflows that need command history, incremental state, and a stable PTY.

### Non-blocking health check

```bash
slicer vm health VM_NAME --json    # Agent version, uptime, stats — does not block
```

---

## Running Commands

### Execute a command (foreground)

```bash
slicer vm exec VM_NAME -- "whoami"
```

`slicer vm exec` blocks until the command exits and streams stdout/stderr inline.
For long-running processes that should survive client disconnect (dev servers,
multi-minute builds, agent-driven workflows), use `slicer vm bg exec` instead —
see [Background Exec](#background-exec-long-running-processes) below.

By default, `slicer vm exec` executes the command through a shell, so use direct command strings.
For plain exec with no shell interpretation, use `--shell ""`.
Avoid wrapping with `/bin/bash -lc` or explicit shell launches unless you intentionally need shell-specific parsing.
Anti-pattern: `slicer vm exec ... -- /bin/bash -lc "..."` (unless required for nested shell logic).

The default user is auto-detected (typically `ubuntu`, uid 1000). Override with `--uid`:

```bash
slicer vm exec VM_NAME --uid 1000 -- "sudo apt update && sudo apt install -y nginx"
```

Key flags:

| Flag | Purpose |
|------|---------|
| `--uid` | Run as target user UID (non-root default is auto-detected, typically `1000`) |
| `--cwd string` | Set working directory (`~` and `~/path` supported, `../` traversal is blocked) |
| `--env stringArray` | Pass environment variables as `KEY=VALUE` pairs (repeatable) |
| `--shell ""` | Skip shell interpreter, exec directly |

`--cwd` and `--env` are direct `slicer vm exec` flags (confirmed from `slicer vm exec --help`).

Example:

```bash
slicer vm exec VM_NAME --uid 1000 --cwd ~/project --env FOO=bar --env DEBUG=1 -- "env | sort | head -n 5"
```

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

Flags (from `slicer vm shell --help`): `--uid`, `--cwd`, `--shell`, `--bootstrap "command"` (run on connect).

- `--env` is **not** a `slicer vm shell` flag; pass env vars inside the shell once connected or use `slicer vm exec --env`.
- `--shell` in `slicer vm shell` is shell-choice only; do not assume `zsh` is installed.

Use `slicer vm shell` for longer interactive work; keep `slicer vm exec` for bounded command calls.
It opens an interactive PTY, so it is not suited to non-interactive stdin pipelines.

### Background Exec (long-running processes)

Use `slicer vm bg exec` when the command should survive client disconnect — dev servers, builds, test runs.
Do **not** use `slicer vm exec ... &` — that ties the child to the local shell and you can't reconnect.

**Critical difference from `vm exec`:** `bg exec` defaults to **direct exec** (no shell).
`vm exec` defaults to `/bin/bash`. This means:
- Positional: pass binary + args as separate tokens. `-- npm run dev` ✓. `-- "npm run dev"` ✗ (error).
- Shell features needed? Use `--shell=/bin/bash`. For daemons, prefix with `exec`: `--shell=/bin/bash -- "cd /app && exec ./server"`.
- Explicit form (`-c`/`-a`): always direct-exec, no quoting issues, mutex with `--shell` and positional.

**Three command forms:**

```bash
# 1. Positional — separate tokens after --
slicer vm bg exec VM_NAME --uid 1000 -- npm run dev

# 2. Explicit — preferred for agents
slicer vm bg exec VM_NAME --uid 1000 -c npm -a run -a dev

# 3. Shell — opt-in for $VAR, pipes, &&
slicer vm bg exec VM_NAME --uid 1000 --shell=/bin/bash -- "cd /app && exec npm run dev"
```

**Capture exec_id** for later management:

```bash
EX=$(slicer vm bg exec VM_NAME --uid 1000 --cwd /home/ubuntu/app \
     -- npm run dev \
     | awk -F'[= ]' '/exec_id=/ {for (i=1;i<=NF;i++) if ($i=="exec_id") print $(i+1)}')
```

**Management subcommands:**

```bash
slicer vm bg list   VM_NAME                     # list running + exited
slicer vm bg info   VM_NAME "$EX"               # JSON status of one exec
slicer vm bg logs   VM_NAME "$EX"               # dump ring buffer (--follow to stream)
slicer vm bg wait   VM_NAME "$EX" --timeout 10m # block until exit
slicer vm bg kill   VM_NAME "$EX"               # SIGTERM (→ SIGKILL after 5s)
slicer vm bg remove VM_NAME "$EX"               # free buffer — always do when done
```

Key flags: `--uid`, `--cwd`, `--env KEY=VALUE`, `--ring-bytes 4M` (buffer cap, default 1M), `--follow`, `--json`. If binary not on `$PATH`, use full path: `-- /usr/local/bin/nats-server -p 4222`.

See [references/bg-exec.md](references/bg-exec.md) for the full flag table, ring buffer details, and worked examples.

---

## File Transfer

### Copy files to/from VMs

```bash
# Single file (no `-r` needed)
slicer vm cp ./local-file.txt VM_NAME:/tmp/file.txt --uid 1000

# Single file from VM
slicer vm cp VM_NAME:/etc/os-release ./os-release.txt

# Single file with custom permissions (binary mode only)
slicer vm cp ./script.sh VM_NAME:/tmp/script.sh --mode=binary --permissions 0755 --uid 1000

# Whole directory — prefer the top-level shortcut + `-r`
# (use this instead of `slicer vm cp --mode=tar` when copying folders)
slicer cp -r ./my-project/ VM_NAME:/home/ubuntu/project/ --uid 1000

# Directory with exclusions
slicer cp -r ./src/ VM_NAME:/home/ubuntu/src/ --uid 1000 \
  --exclude '**/.git/**' --exclude '**/node_modules/**'
```

Key flags:

| Flag | Purpose |
|------|---------|
| (no `-r`) | Copy single files (common/default usage) |
| `-r` / `--recursive` | Copy recursively using tar mode. Shortcut for `--mode=tar`. |
| `--mode=binary` | Binary mode — supports files (not folders) and enables `--permissions` |
| `--mode=binary --permissions 0755` | Binary mode with custom file permissions |
| `--uid 1000` | File ownership |
| `--exclude 'pattern'` | Glob exclude patterns (tar mode only, repeatable) |

Notes (from `slicer vm cp --help`):
- In tar mode host → VM, patterns from `.slicerignore` in the local source directory are applied in addition to `--exclude`.
- In tar mode VM → host, the local destination is treated as a directory and will be created automatically if it does not exist.

Practical guidance:
- If copies are slow or huge, add a `.slicerignore` file in the directory you copy from (often your repo root) to skip heavyweight paths you don't need inside the VM.
- Treat it like a `.gitignore` for `slicer cp -r` / tar-mode transfers (it cuts upload size and time).
- Typical entries include build outputs and dependency caches such as `bin/`, `node_modules/`, `dist/`, `build/`, `.next/`, `target/`, `vendor/`, and large datasets/artifacts.

---

## Port Forwarding

Forward traffic from VMs to your local machine with `slicer vm forward` (the command is `forward`, not `port-forward`), using `-L` (SSH-style) syntax.

```bash
# Always check the local host port is free before forwarding.
PORT=8080
if command -v lsof >/dev/null 2>&1; then
  if lsof -i TCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Local port $PORT is already in use. Pick a different host port (for example 18080)."
    exit 1
  fi
else
  echo "Cannot validate local port availability (lsof not installed); proceed with caution."
fi

# TCP port forward
slicer vm forward VM_NAME -L 8080:127.0.0.1:8080

# Remap host port
slicer vm forward VM_NAME -L 3000:127.0.0.1:8080

# Supported mapping forms:
# - TCP -> TCP: LOCAL_HOST:LOCAL_PORT:REMOTE_HOST:REMOTE_PORT
# - Unix socket -> TCP: LOCAL_HOST:LOCAL_PORT:REMOTE_SOCKET
# - Unix socket -> Unix socket: LOCAL_SOCKET:REMOTE_SOCKET
# Unix socket → local TCP (e.g. Docker)
slicer vm forward VM_NAME -L 127.0.0.1:2375:/var/run/docker.sock

# Unix socket → local Unix socket
slicer vm forward VM_NAME -L /tmp/docker.sock:/var/run/docker.sock

# SSH access
slicer vm forward VM_NAME -L 2222:127.0.0.1:22

# Privileged VM services (e.g. nginx on 80/443) should use high host ports unless requested otherwise.
slicer vm forward VM_NAME -L 8080:127.0.0.1:80
slicer vm forward VM_NAME -L 8443:127.0.0.1:443

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
