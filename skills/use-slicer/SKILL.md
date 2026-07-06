---
name: use-slicer
description: Use Slicer to launch Linux microVMs for sandboxed builds, E2E tests, Docker, CI, and isolated dev environments — works from macOS and Linux hosts
tools: [Bash]
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

On macOS, the CLI drives **Slicer for Mac** — a persistent Linux VM plus an `sbox` host group for sandboxes. See [references/macos.md](references/macos.md).

## Reference files

Deeper material is split into reference files — read the relevant one when a task calls for it:

- [references/macos.md](references/macos.md) — Slicer for Mac (slicer-mac)
- [references/daemon-setup.md](references/daemon-setup.md) — generate a config and run your own daemon
- [references/workflows.md](references/workflows.md) — worked recipes (E2E, Docker, builds, k3s, DB, SSH)
- [references/custom-images.md](references/custom-images.md) — custom rootfs images and userdata
- [references/bg-exec.md](references/bg-exec.md) — background exec detail
- [references/interactive-tui.md](references/interactive-tui.md) — driving interactive TUIs and coding agents (guest tmux via exec, or host tmux + vm shell)
- [references/networking.md](references/networking.md) — bridge, isolated, and macvtap (LAN-direct) networking
- [references/agent-sandboxes.md](references/agent-sandboxes.md) — coding-agent sandbox detail

Companion skills: **`use-slicer-worktrees`** (git worktrees in a VM), **`use-slicer-proxy`** (filtered egress + secret injection).

## Prerequisites — You Need a Running Daemon

Slicer is **not a SaaS** — it requires a running daemon that manages VMs.

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

### Connecting to a daemon

**macOS — slicer-mac.** If slicer-mac is installed the daemon is already running and the socket auto-detects — no flags needed. Launch sandboxes into the `sbox` host group. See [references/macos.md](references/macos.md).

**Slicer Box — hosted.** A managed instance included with Slicer Home Edition — one persistent VM (2 vCPU, 4GB RAM, 10GB disk) over HTTPS:

```bash
export SLICER_URL=https://box.slicervm.com
export SLICER_TOKEN_FILE=~/.slicer/gh-access-token   # a GitHub personal access token
```

You get one VM to recycle; its disk persists between sessions (installed packages, files, services). Factory-reset by `slicer vm delete VM_NAME` then `slicer vm launch` + `slicer vm ready`.

**Existing Linux daemon.** Connect to a daemon already running locally or on the LAN. **Ask the user** for the URL and token path — don't guess.

```bash
# Local unix socket (no auth; may need sudo to read the socket)
export SLICER_URL=/path/to/slicer.sock

# Local or remote TCP
export SLICER_URL=http://127.0.0.1:8080
export SLICER_TOKEN_FILE=/var/lib/slicer/auth/token   # may need sudo to read
# or pass the value directly:
export SLICER_TOKEN=$(sudo cat /var/lib/slicer/auth/token)
```

Check for a running daemon with `ps aux | grep -E "slicer|firecracker" | grep -v grep`. If the user supplies `SLICER_TOKEN` / `SLICER_TOKEN_FILE` or a specific endpoint, use those exactly and do not infer defaults.

**No daemon running?** To generate a config and start your own — locally or over SSH — see [references/daemon-setup.md](references/daemon-setup.md).

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
| `--persistent` | Keep VM state across daemon restarts/shutdowns (default `true`); pass `--persistent=false` for ephemeral |

Important: do not use readiness flags on `slicer vm add`. If startup blocking or readiness is required, run `slicer vm ready <VM_NAME>` as a separate step.

When creating VMs for mutable tasks, do not target or reuse `slicer-1` on slicer-mac unless the user explicitly requests it. Reuse the session's tagged VM when known; otherwise create a new VM with explicit `--tag`.

### Persistent temporary VMs

VMs created with `slicer vm add` are persistent by default, they survive daemon restarts and shutdowns. Pair every launch with descriptive `--tag`s so the sandbox can be rediscovered later. Pass `--persistent=false` only when you want a one-shot ephemeral VM that disappears with the daemon.

**On slicer-mac**: launch into the `sbox` host group explicitly — the `slicer` group is reserved for the persistent Linux twin.

```bash
VM_NAME=$(slicer vm add sbox \
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
   slicer vm add <group> --tag "workflow=..." ...
   ```
2. Or skip the check and launch into the default group by omitting the positional arg:
   ```bash
   slicer vm add --tag "workflow=..." ...
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

See [references/networking.md](references/networking.md) for bridge, isolated, and macvtap (LAN-direct) networking.

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

Slicer can provision a fresh microVM, install a coding agent into it, and — depending on the argument — sync your workspace and attach a session.

```bash
slicer workspace [./path|vm]   # Plain VM + shell (no agent)
slicer amp       [./path|vm]   # Amp sandbox
slicer claude    [./path|vm]   # Claude Code sandbox
slicer codex     [./path|vm]   # Codex sandbox
slicer opencode  [./path|vm]   # OpenCode sandbox
slicer copilot   [./path|vm]   # GitHub Copilot CLI sandbox
```

### Three ways to run

The single optional argument selects the mode:

- **No argument → provision-only.** Creates a VM, syncs your git identity, copies the agent's credentials in, and installs the agent — then stops. Nothing is copied from the host and no session is attached. Use this for a clean agent VM, then push code in with `slicer wt push` (see the `use-slicer-worktrees` skill).
- **A local directory → workspace copy.** Provisions as above, then tar-copies that directory in (honouring `.slicerignore`) and attaches the agent session.
- **A VM name → reattach.** Anything that is not a local path is treated as an existing VM name; waits for the agent and reattaches.

```bash
slicer codex                 # provision-only: VM + codex + creds, then stop
slicer codex ./my-project    # copy ./my-project in, then attach
slicer codex codex-1         # reattach to existing VM codex-1
```

> **Behaviour change:** bare `slicer codex` (no argument) no longer copies the current directory — it is now **provision-only**. Pass `.` explicitly (`slicer codex .`) to copy the cwd, or use the worktree flow below.

`slicer workspace` follows the same three modes but installs no agent. Each agent command copies that tool's auth/config files in and installs the agent via `arkade`.

Session modes: `--tmux none` (default), `--tmux local`, `--tmux remote`.

Use `.slicerignore` at the workspace root to exclude files (same syntax as `.gitignore`).

See [references/agent-sandboxes.md](references/agent-sandboxes.md) for credential paths, flags, and the worktree workflow.

## Related skills

Two companion skills cover Slicer features in depth — load them when a task calls for them:

- **`use-slicer-worktrees`** — get a git worktree or repository into a VM with a working, self-contained `.git`, then pull commits back (`slicer wt push` / `pull` / `list`). This is the recommended way to put a git project into a provision-only agent sandbox.
- **`use-slicer-proxy`** — filter, audit, and inject secrets into HTTP(S) egress from VMs with Slicer Proxy: default-deny allow rules, credential injection (Bearer, Basic, OAuth), and audit / passthrough modes, on Linux and macOS.

---

## Common Workflows

Worked recipes — E2E tests, remote Docker, cross-compiling Go/Rust, k3s clusters, database testing, SSH/SCP — are in [references/workflows.md](references/workflows.md).

---

## Custom Images & Userdata

The default image list, building a custom rootfs (`slicer disk export` → OCI image), and userdata (cloud-init style first-boot scripts) are covered in [references/custom-images.md](references/custom-images.md).

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

See [references/custom-images.md](references/custom-images.md) for building a custom rootfs image.

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
