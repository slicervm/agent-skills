# Background Exec Reference

## Key flags for `slicer vm bg exec`

| Flag | Purpose |
|------|---------|
| `--uid` | User ID (default: auto-detect non-root) |
| `--gid` | Group ID (default: auto-detect non-root) |
| `--cwd` | Working directory (default: user home) |
| `--env KEY=VALUE` | Environment variable (repeatable) |
| `--shell`, `-s` | Shell interpreter (default: empty = direct exec). Set to `/bin/bash` for `$VAR` expansion, globs, pipes. Use `exec` in the shell string for clean PID. |
| `--cmd`, `-c` | Binary to exec (explicit form, mutex with positional and `--shell`) |
| `--arg`, `-a` | Argument to pass to `--cmd` (repeatable, order-preserving) |
| `--ring-bytes 4M` | Per-process ring buffer cap (default 1M) |
| `--follow` | Stream logs after launch until exit |
| `--json` | Emit JSON output (for scripting) |

## Capture the launch ID

Use `--json` and extract `.exec_id` with `jq`, as in the examples below.
Human-readable output uses labels such as `Exec ID`, not `exec_id=...`;
its layout is not a scripting interface. The examples use Bash's `pipefail`
and reject missing, empty, or non-string IDs before running management commands.

Do not combine ID capture with `--follow`: it emits further events and stays
attached until the child exits. Launch detached, save the ID, then use
`bg logs --follow` separately. Do not merge stderr into JSON stdout with `2>&1`.

If ID capture fails after the job may have launched, use
`slicer vm bg list "$VM_REF" --json`, then `bg info` to confirm the command
and start time of the intended job. Recover that ID before continuing; do not
relaunch blindly or assume the first listed process belongs to this task.

## Ring buffer

- Stdout + stderr captured into a per-process ring buffer (default 1 MiB, ~10 000 lines).
- Bump with `--ring-bytes 4M` for verbose builds (e.g. `docker buildx`).
- When full, oldest frames are evicted. Reconnecting readers see a `type=gap` frame before output resumes.
- Buffer lives until explicit `slicer vm bg remove`. After reap, calls return `410 Gone`.
  `remove` does not stop a running child: check `bg info` or `bg wait`, and kill
  it first when necessary. Removing a live entry discards the control handle
  while the process continues in the guest.
- Agent-wide cap: 256 MiB across all background execs. Exceeding it returns `503`.

## Additional notes

- Detached at launch — killing the `slicer` CLI does not kill the child.
- `--follow --from-id N` resumes after disconnect.
- Callers that launch many execs and never reap them grow agent memory. Always `vm bg remove` when done.
- v1 scope: if the guest agent exits, its registry is lost and children die. Fine for CI jobs and dev servers; not for daemonised services across reboots.

## Example: dev server with port forward

```bash
VM_REF=dev-1

# Start the dev server in background (explicit form — preferred for agents)
set -o pipefail
EX=$(slicer vm bg exec "$VM_REF" --uid 1000 --cwd /home/ubuntu/app --json \
     -c npm -a run -a dev \
     | jq -er '.exec_id | select(type == "string" and length > 0)') || exit 1

# Port-forward to access it from the host
slicer vm forward "$VM_REF" -L 3000:127.0.0.1:3000 &

# Check logs later
slicer vm bg logs "$VM_REF" "$EX" --follow

# When done, stop and clean up
slicer vm bg kill "$VM_REF" "$EX"
slicer vm bg wait "$VM_REF" "$EX" --timeout 10s
slicer vm bg remove "$VM_REF" "$EX"
```

CLI 0.1.216 and later accept friendly names across background management
commands. `VM_REF` can be the friendly name assigned with `--name` or the
canonical hostname. Update older clients which require a canonical hostname
for `bg kill`.

## Example: long-running build

```bash
VM_REF=build-1

# Launch build, follow output until it exits (CLI exit code = child exit code)
slicer vm bg exec "$VM_REF" --uid 1000 --ring-bytes 4M --follow \
  -- docker build -t myapp:latest .

# Or launch detached and wait for it
set -o pipefail
EX=$(slicer vm bg exec "$VM_REF" --uid 1000 --ring-bytes 4M --json \
     -- make build-all \
     | jq -er '.exec_id | select(type == "string" and length > 0)') || exit 1

# Do other work, then check back
slicer vm bg wait "$VM_REF" "$EX" --timeout 30m
slicer vm bg logs "$VM_REF" "$EX"       # dump final output
slicer vm bg remove "$VM_REF" "$EX"     # reap
```
