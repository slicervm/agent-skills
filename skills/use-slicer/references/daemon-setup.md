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

Socket: `~/slicer-mac/slicer.sock`. Auth: off by default. See [workflows-and-admin.md](workflows-and-admin.md) for more slicer-mac examples.

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
