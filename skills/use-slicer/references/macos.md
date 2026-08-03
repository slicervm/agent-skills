# Slicer on macOS (slicer-mac)

The Slicer CLI also works as a client for **Slicer for Mac**, which runs Linux microVMs on Apple Silicon or Intel Macs.

## Overview

- Slicer for Mac ships a persistent Linux VM named `slicer-1` for local development and testing, with a permanent disk — analogous to WSL2.
- Two fixed host groups:
  - `slicer` — the persistent VM (`slicer-1`), a Linux twin that survives reboots
  - `sbox` — ephemeral host group for API-launched sandbox VMs
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
VM_NAME=$(slicer vm add sbox | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" --uid 1000 -- "make test"
slicer vm delete "$VM_NAME"
```

Do not target or reuse `slicer-1` for mutable tasks unless the user explicitly asks. Reuse the session's tagged VM when known; otherwise create a new VM with an explicit `--tag`.

## Slicer Proxy on macOS

For filtered egress and secret injection, see the `use-slicer-proxy` skill — note that on macOS egress blocking is off by default and requires edits to `slicer-mac.yaml`.
