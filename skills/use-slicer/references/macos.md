# Slicer on macOS (slicer-mac)

The Slicer CLI also works as a client for **Slicer for Mac**, which runs Linux microVMs on Apple Silicon or Intel Macs.

## Overview

- Slicer for Mac ships a persistent Linux VM named `slicer-1` for local development and testing, with a permanent disk — analogous to WSL2.
- Two fixed host groups:
  - `slicer` — the persistent VM (`slicer-1`), a Linux twin that survives reboots
  - `sbox` — on-demand host group for sandbox VMs
- **Socket**: auto-detected at `~/slicer-mac/slicer.sock` — no `--url` needed.
- **Auth**: disabled by default for the local socket — no `--token` needed.
- **Networking**: VMNet — VMs cannot talk to each other, but the host can talk to VMs. Reach a VM's TCP ports by the IP shown in `slicer vm list`, or with `slicer vm forward` (SSH `-L` / `kubectl port-forward` style, for TCP and UNIX sockets).
- **Install**: `slicer install slicer-mac ~/slicer-mac`
- **Cold forking**: not yet supported. Slicer for Mac can suspend and restore a VM, but cannot commit its disk and fork children from it.

## Connecting

If slicer-mac is installed the daemon is already running — no setup, no flags:

```bash
slicer info
slicer vm list
```

## Launching VMs

Always launch API-created microVMs into the explicit `sbox` host group — the `slicer` group is reserved for the persistent `slicer-1` twin:

```bash
VM_NAME=$(slicer vm add sbox --tag "workflow=smoke" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" --uid 1000 -- "uname -a"

# Ephemeral sandbox
VM_NAME=$(slicer vm add sbox --persistent=false | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" --uid 1000 -- "make test"
slicer vm delete "$VM_NAME"
```

Use `--name` when a human-readable CLI reference is useful:

```bash
slicer vm add sbox --name smoke-test --tag workflow=smoke --wait
slicer shell smoke-test
slicer vm delete smoke-test
```

The generated `sbox-N` hostname remains the slicer-mac API identity.
`smoke-test` is stored as the immutable `name=smoke-test` tag and resolved by
the Slicer CLI. slicer-mac persists tags but does not expose an alias route or
a separate name resource.

The built-in `slicer-1` VM can receive a friendly name once because it is not
created through `slicer vm add`:

```bash
slicer vm tag add slicer-1 --tag name=linux-twin
slicer shell linux-twin
```

The assigned name cannot be changed or removed.

Do not target or reuse `slicer-1` for mutable tasks unless the user explicitly asks. Reuse the session's tagged VM when known; otherwise create a new VM with an explicit `--tag`.

## Slicer Proxy on macOS

For filtered egress and secret injection, see the `use-slicer-proxy` skill — note that on macOS egress blocking is off by default and requires edits to `slicer-mac.yaml`.
