# Slicer on macOS (slicer-mac)

The Slicer CLI also works as a client for **Slicer for Mac**, which runs Linux microVMs on Apple Silicon or Intel Macs.

## Overview

- Slicer for Mac ships a persistent Linux VM named `slicer-1` for local development and testing, with a permanent disk — analogous to WSL2.
- Two fixed host groups:
  - `slicer` — the persistent VM (`slicer-1`), a Linux twin that survives reboots
  - `sbox` — on-demand host group for sandbox VMs
- **Socket**: auto-detected at `~/slicer-mac/slicer.sock` — no `--url` needed.
- **Auth**: disabled by default for the local socket — no `--token` needed.
- **Networking**: Apple VZ NAT by default — VMs cannot talk to each other, but the host can talk to VMs. Reach a networked VM's TCP ports by the IP shown in `slicer vm list`, or with `slicer vm forward` (for TCP and UNIX sockets). Supported builds accept `--network none` for `sbox` VMs with no NIC or IP lease; management remains available over vsock.
- **Install**: `slicer install slicer-mac ~/slicer-mac`
- **Cold forking**: supported for stopped, persistent `sbox` VMs through the
  same `slicer vm commit` and `slicer vm fork` commands used on Linux.

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
slicer vm exec "$VM_NAME" -- "uname -a"

# Ephemeral sandbox
VM_NAME=$(slicer vm add sbox --persistent=false | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" -- "make test"
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

To run Slicer inside a Mac-hosted Linux VM, read the
[nested virtualization setup](nested-virtualization.md#enable-nested-virtualization-on-slicer-for-mac)
before launching it. It covers hardware requirements, `nested_virt`, daemon
restart, and guest KVM checks.

## Cold forking `sbox` VMs

For an online builder and a completely offline runner, read
[offline-vms.md](offline-vms.md): prepare with host-group networking, stop
and commit, then fork with `--network none`. Request `none` for every offline
fork. Omission or an empty value uses VZ NAT, even from an offline source.

Prepare and stop a persistent `sbox` VM, commit it, then fork independent APFS
copy-on-write children. Follow the
[cold-fork guidance](cold-forking.md#agent-safe-workflow), or the
[proxy recipe](cold-forking.md#macos-with-slicer-proxy) when the host group is
forced through Slicer Proxy.

The shared CLI and SDK contract includes cache keys, tags, identity fixups,
secret filtering, persistent or ephemeral children, waits, and CPU/RAM
overrides. The macOS backend is disk-only and supports `sbox` only.

Network allow/drop settings apply to networked `sbox` VMs as a group, so macOS
does not accept the Linux per-fork `--allow`, `--no-allow`, and `--drop`
overrides. When runners need selective network access, force the host group
through Slicer Proxy, use an open client while preparing a hot builder, and
give each cold-forked runner a different default-deny or restricted client.
Offline (`none`) VMs cannot reach Slicer Proxy. Never commit the hot client
token into the builder disk.
See [cold-forking.md](cold-forking.md) for cleanup, cache, and proxy-client
guidance.

## Slicer Proxy on macOS

For filtered egress and secret injection, see the `use-slicer-proxy` skill.
On macOS, egress blocking is off by default and requires edits to
`slicer-mac.yaml`; those settings apply to the complete `sbox` host group.
