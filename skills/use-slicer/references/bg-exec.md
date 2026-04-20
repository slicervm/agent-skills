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

## Ring buffer

- Stdout + stderr captured into a per-process ring buffer (default 1 MiB, ~10 000 lines).
- Bump with `--ring-bytes 4M` for verbose builds (e.g. `docker buildx`).
- When full, oldest frames are evicted. Reconnecting readers see a `type=gap` frame before output resumes.
- Buffer lives until explicit `slicer vm bg remove`. After reap, calls return `410 Gone`.
- Agent-wide cap: 256 MiB across all background execs. Exceeding it returns `503`.

## Additional notes

- Detached at launch — killing the `slicer` CLI does not kill the child.
- `--follow --from-id N` resumes after disconnect.
- Callers that launch many execs and never reap them grow agent memory. Always `vm bg remove` when done.
- v1 scope: if the guest agent exits, its registry is lost and children die. Fine for CI jobs and dev servers; not for daemonised services across reboots.

## Example: dev server with port forward

```bash
VM_NAME=dev-1

# Start the dev server in background (explicit form — preferred for agents)
EX=$(slicer vm bg exec "$VM_NAME" --uid 1000 --cwd /home/ubuntu/app \
     -c npm -a run -a dev \
     | awk -F'[= ]' '/exec_id=/ {for (i=1;i<=NF;i++) if ($i=="exec_id") print $(i+1)}')

# Port-forward to access it from the host
slicer vm forward "$VM_NAME" -L 3000:127.0.0.1:3000 &

# Check logs later
slicer vm bg logs "$VM_NAME" "$EX" --follow

# When done, stop and clean up
slicer vm bg kill "$VM_NAME" "$EX"
slicer vm bg remove "$VM_NAME" "$EX"
```

## Example: long-running build

```bash
VM_NAME=build-1

# Launch build, follow output until it exits (CLI exit code = child exit code)
slicer vm bg exec "$VM_NAME" --uid 1000 --ring-bytes 4M --follow \
  -- docker build -t myapp:latest .

# Or launch detached and wait for it
EX=$(slicer vm bg exec "$VM_NAME" --uid 1000 --ring-bytes 4M \
     -- make build-all \
     | awk -F'[= ]' '/exec_id=/ {for (i=1;i<=NF;i++) if ($i=="exec_id") print $(i+1)}')

# Do other work, then check back
slicer vm bg wait "$VM_NAME" "$EX" --timeout 30m
slicer vm bg logs "$VM_NAME" "$EX"       # dump final output
slicer vm bg remove "$VM_NAME" "$EX"     # reap
```
