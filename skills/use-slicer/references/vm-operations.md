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

See [bg-exec.md](bg-exec.md) for the full flag table, ring buffer details, and worked examples.

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

See [networking.md](networking.md) for bridge vs isolated networking.

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
