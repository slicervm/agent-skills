# Offline VMs on macOS and Linux

Prepare dependencies with networking, commit the stopped VM's disk, then fork
offline runners with no virtual NIC. Supported builds provide this for macOS
`sbox` VMs and Linux Firecracker VMs. On macOS, the built-in `slicer-1` keeps
VZ NAT. Linux Cloud Hypervisor, QEMU, and hot (memory) forks
do not support `none`; use a disk commit for offline forks.

## Check support

Use a Slicer CLI and daemon that implement network attachment selection
for the target platform. Check the installed client before constructing
commands:

```bash
slicer version
slicer info
slicer vm add --help
slicer vm fork --help
```

Both commands must expose `--network`. Client support alone does not establish
daemon support. For an offline VM, check that `slicer vm describe VM_REF --json`
reports `network.mode: "none"` and an empty `ip` before copying inputs or
running the workload. If the daemon rejects the request or the VM has
networking, stop and use compatible client and daemon versions. Do not
silently omit `none` after an error.

## Network selection

`none` is the only non-empty `--network` value on both platforms:

| Selection on creation or disk fork | Result |
|------------------------------------|--------|
| `--network none` | No NIC or IP lease |
| Omit `--network`, or use `--network=""` | Host-group networking (VZ NAT on macOS) |

Request `--network none` for every offline fork, even when the source VM
was offline. The source or commit does not determine the child's attachment.
Omit the flag to create a networked fork for updating dependencies.

A VM keeps its attachment across shutdown/relaunch; Linux suspend/restore
also preserves it across daemon restarts. These operations resume the same
VM, whereas a fork selects networking anew.

Linux disk commits and forks require a bridge or isolated host group, even
for offline VMs. CNI/macvtap groups support offline creation, but cannot
commit or fork. Offline host groups are unsupported; select `none` per VM.

VM descriptions report `network.mode: "none"` for offline VMs. Linux also
reports `network.override.mode: "none"` for the saved no-NIC attachment;
online attachments omit that override field. macOS reports `"nat"` for VZ
NAT; description values are not network-selection arguments.

Do not combine `none` with an explicit IP or allow/drop overrides, even empty
lists. Linux offline forks clear inherited firewall overrides; online forks
retain them. macOS rejects per-VM allow/drop policies.

## Prepare online, then fork offline

This example uses Ubuntu, local `jq`, and an already running daemon. On
macOS, use `GROUP=sbox`. On Linux, set `GROUP` to an existing Firecracker
bridge or isolated host group. Use the session's configured endpoint or
local socket auto-detection.

The builder needs outbound access for package installation; if macOS `sbox` is
forced through Slicer Proxy, follow the hot-client setup in
[cold-forking.md](cold-forking.md#macos-with-slicer-proxy) during preparation
and remove its token before committing.

Shutdown is asynchronous. The example polls the builder's state up to 30
times, two seconds apart, before committing. A failed lookup or a VM that
does not reach `Stopped` ends the workflow rather than racing commit against
shutdown. Use the same check before relaunching a VM you have just shut down.

```bash
set -e -o pipefail
# Linux: replace sbox with an existing Firecracker bridge or isolated group.
GROUP=sbox
WORKFLOW=offline-jq-$(date +%Y%m%d-%H%M%S)
BUILDER_REF="$WORKFLOW-builder"
RUNNER_REF="$WORKFLOW-runner"

BUILDER_HOSTNAME=$(slicer vm add "$GROUP" --name "$BUILDER_REF" \
  --tag "workflow=$WORKFLOW" --persistent \
  --wait --json | jq -er '.hostname')
slicer vm exec "$BUILDER_REF" --uid 0 -- \
  "apt-get update && apt-get install -y jq"

slicer vm shutdown "$BUILDER_REF"
for attempt in $(seq 1 30); do
  VM_JSON=$(slicer vm describe "$BUILDER_REF" --json) || exit 1
  VM_STATE=$(printf '%s\n' "$VM_JSON" | jq -er '.status') || exit 1
  [ "$VM_STATE" = Stopped ] && break
  sleep 2
done
if [ "$VM_STATE" != Stopped ]; then
  echo "VM did not stop; leaving it intact without committing" >&2
  exit 1
fi
COMMIT=$(slicer vm commit "$BUILDER_REF" --json | jq -er '.commit_id')
# The committed disk remains usable after source deletion.
slicer vm delete "$BUILDER_REF"

RUNNER_HOSTNAME=$(slicer vm fork "$COMMIT" --name "$RUNNER_REF" \
  --tag "workflow=$WORKFLOW" --network none --wait --json | jq -er '.hostname')
slicer vm describe "$RUNNER_REF" --json |
  jq -e '.network.mode == "none" and (.ip == null or .ip == "")' >/dev/null
slicer vm exec "$RUNNER_REF" -- jq --version
slicer vm exec "$RUNNER_REF" -- ls /sys/class/net

# Native file copy also works without an IP address.
slicer vm exec "$RUNNER_REF" -- "jq --version > /tmp/jq-version.txt"
slicer vm cp "$RUNNER_REF":/tmp/jq-version.txt "./$WORKFLOW-jq-version.txt"
```

If the network check fails, the example stops before running the workload,
leaving the runner available for inspection.

An offline guest has no hardware NIC; software interfaces such as `lo` and
`dummy0` can still appear. No IP lease is allocated. Use agent readiness and
health checks instead of waiting for an IP or testing SSH connectivity.

The source hostname and child hostname are separate API identities; keep the
chosen friendly references for CLI operations. Deleted source hostnames can
be reused, so do not rediscover or delete the source by its old hostname later.

After collecting the result, delete the runner. Keep the commit for reuse,
or delete it after all children and the source have been deleted:

```bash
slicer vm delete "$RUNNER_REF"
slicer vm commit delete "$COMMIT" # Only when the cached disk is no longer needed.
```

To create a fresh offline VM, use the selected host group without a commit:

```bash
slicer vm add "$GROUP" --name "offline-$(date +%Y%m%d-%H%M%S)" \
  --tag workflow=offline --network none --wait
```

## What remains available

Shell, exec, background exec, file copy, health, agent readiness, userdata
wait, shutdown, and relaunch remain available through Slicer's vsock
management path. Forwarding to guest loopback services also works without
a guest IP or SSH connection.

On Linux, offline boots skip DNS/DHCP configuration and guest GitHub SSH-key
downloads; supply keys directly if needed. `vm top` is unavailable because
`slicer-vmmeter` is masked for that boot. The mask does not carry into an
online cold fork.

The guest cannot reach the internet, the host's network services, or Slicer
Proxy. Install packages and download dependencies, container images, and
other required inputs while preparing the online builder, or copy files via
`slicer vm cp`. Userdata and workloads must work offline; a script that runs
`apt-get`, downloads a toolchain, or calls a remote model API cannot rely on
network access. Do not configure a proxy client as an offline connectivity fix.

## API requests

For `POST /hostgroup/<group>/nodes` and `POST /vm/commits/<commit-id>/fork`,
use `{"network":{"mode":"none"}}` for no NIC. Omit `network` or leave
`network.mode` empty to use host-group networking on creation and forks.
Each offline fork must explicitly request `none`.
