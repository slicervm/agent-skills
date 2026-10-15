# Nested virtualization

Use this reference when:

- Your workstation runs macOS or Windows and you want to run **Slicer for
  Linux** inside a Linux VM. For the native Slicer for Mac workflow, see
  [macos.md](macos.md).
- Your available infrastructure is a cloud VM, for example on DigitalOcean,
  Azure, or Google Cloud Platform (GCP). Choose an instance that exposes nested
  virtualization and verify `/dev/kvm`; support depends on the instance type.
- You want Slicer within Slicer for testing and experimentation, including
  installation, daemon changes, VM lifecycle operations, and E2E tests.

For the first two cases, install and run Slicer in the existing Linux VM using
[daemon-setup.md](daemon-setup.md) once KVM is available. The recipe below is
for the third case, where a Slicer-managed VM hosts another Slicer daemon.
Provisioning a KVM-capable Windows or cloud environment is outside this reference;
those cases assume an existing Linux VM with working `/dev/kvm`.

## Slicer within Slicer

Use nested virtualization to test Slicer installation, daemon changes, VM
lifecycle operations, or end-to-end workflows inside a disposable Slicer VM.
This works with a Linux outer host or Slicer for Mac when the outer guest has
KVM support. The inner daemon always runs Slicer for Linux.

```text
Linux Slicer / Slicer for Mac
└── outer Linux VM: test runner, /dev/kvm, inner Slicer daemon
    └── inner Linux VMs: workloads under test
```

See the official [nested virtualization guide](https://docs.slicervm.com/tasks/nested-virtualization/#prerequisites).

## Prerequisites

- Choose non-overlapping outer and inner subnets, also avoiding LAN/VPN routes.
  Use different host group names: Slicer derives MAC addresses from these names.
- Budget outer RAM and disk for the inner daemon, downloaded images, and all
  concurrent inner VMs. For one 1 GiB inner smoke-test VM, a 4 GiB outer VM is a
  useful starting point; increase it for larger tests.
- KVM must be available **inside the outer VM**, not just on the physical host.
  On Linux, the host CPU/hypervisor must expose nested virtualization. On Mac,
  the hardware, macOS, and Slicer for Mac must support exposing it to Linux.
  Verify `/dev/kvm` in the guest before installing the inner daemon.
- Have a Slicer license file available to copy into the test VM. Install the
  Linux binary matching the guest architecture; a macOS binary cannot run there.

## 1. Select or create the outer test VM

Run these commands on the workstation using its existing outer-daemon connection.
Reuse this session's tagged test VM by setting `OUTER_VM` to its recorded name.
Otherwise select an appropriate Linux host group with `slicer vm group`, or use
`sbox` on Mac:

```bash
OUTER_GROUP=sbox  # Mac; replace with the selected group on Linux
set -o pipefail
OUTER_CREATED=false
if [ -z "${OUTER_VM:-}" ]; then
  OUTER_VM=$(slicer vm add "$OUTER_GROUP" --tag workflow=nested-slicer --json |
    jq -er '.hostname | select(type == "string" and length > 0)') || exit 1
  OUTER_CREATED=true
fi
printf 'Outer test VM: %s\n' "$OUTER_VM"
slicer vm ready "$OUTER_VM" --timeout 5m || exit $?
```

Keep the recorded name when resuming after an interruption; if readiness fails,
inspect that VM instead of creating a replacement. On a reused VM, inspect its
existing config and `slicer vm bg list` before repeating setup or daemon startup.

On Mac, leave the persistent `slicer-1` twin alone unless it is the requested
target; see [macos.md](macos.md). If Linux has no outer daemon yet, follow
[daemon-setup.md](daemon-setup.md), using a distinct group and subnet such as
`slicer0` and `192.168.130.0/24`.

The remaining examples assume an Ubuntu outer guest with UID 1000. Adjust home
paths and UID for other images, then enter the guest for setup:

```bash
slicer vm shell "$OUTER_VM" --uid 1000
```

## 2. Prepare the inner daemon inside the outer VM

All commands in this section run **inside the outer VM**.

```bash
uname -m
lscpu
ls -l /dev/kvm
ip route
df -h /home/ubuntu
```

If `/dev/kvm` is absent on an x86 guest, load the modules for the CPU vendor
reported by `lscpu`, then check again:

```bash
# Intel only:
sudo modprobe kvm
sudo modprobe kvm_intel

# AMD only (instead of kvm_intel):
sudo modprobe kvm
sudo modprobe kvm_amd
```

Do not use Intel/AMD modules on an Arm guest, including Apple Silicon. If KVM
remains unavailable, resolve nested virtualization support in the outer
host/hypervisor or guest kernel before continuing.

Install Slicer and its dependencies using the [Linux installer](https://docs.slicervm.com/getting-started/install/):

```bash
curl -sLS https://get.slicervm.com | sudo bash
slicer version
mkdir -p /home/ubuntu/nested-slicer
cd /home/ubuntu/nested-slicer

# Example only: confirm this subnet and group do not conflict with the outer
# daemon, guest routes, or any other inner daemon before generating the config.
slicer new nested --count 0 --cpu 1 --ram 1 \
  --cidr 192.168.140.0/24 \
  --socket /home/ubuntu/nested-slicer/slicer.sock > slicer.yaml
exit
```

For testing a development build, install dependencies first, then copy a Linux
binary built for the outer guest's architecture into it. Use that binary
explicitly when launching the daemon and test client. For source-based tests,
use the companion `use-slicer-worktrees` skill or native `slicer vm cp` to move
the project into the outer VM.

## 3. Launch and test the inner daemon

Back on the **workstation**, start the daemon as a tracked background process.
Its working directory contains only this test's configuration and VM disks.
Copy the license to a new root-owned temporary file for this run, preserving any
existing guest license. Record `INNER_LICENSE` for cleanup after an interruption:

```bash
EVAL_DIR=$(mktemp -d "${TMPDIR:-/tmp}/slicer-nested-eval.XXXXXX") || exit $?
printf 'Local test artifacts: %s\n' "$EVAL_DIR"
INNER_LICENSE=$(slicer vm exec "$OUTER_VM" --uid 0 -- \
  'mktemp /tmp/slicer-nested-license.XXXXXX') || exit $?
slicer vm cp ~/.slicer/LICENSE "$OUTER_VM:$INNER_LICENSE" \
  --uid 0 --permissions 0600 || exit $?

set -o pipefail
INNER_EXEC=$(slicer vm bg exec "$OUTER_VM" --uid 0 \
  --cwd /home/ubuntu/nested-slicer --json \
  -c slicer -a --license-file -a "$INNER_LICENSE" \
  -a up -a ./slicer.yaml |
  jq -er '.exec_id | select(type == "string" and length > 0)') || exit 1
slicer vm bg logs "$OUTER_VM" "$INNER_EXEC" || echo 'Could not read daemon logs.' >&2
```

If setup fails, recover before continuing. If license copying failed before
daemon launch, remove the recorded temporary license using the cleanup command
below. If launch-ID capture failed, the daemon may still be running: recover its
ID with `bg list`/`bg info` as described in [bg-exec.md](bg-exec.md#capture-the-launch-id),
then perform cleanup. Do not blindly launch a second daemon.

Still on the **workstation**, write the smoke test and run it through `vm exec`
to capture its exit status. The script runs as root inside the outer VM and
explicitly addresses the inner socket for every client command:

```bash
cat > "$EVAL_DIR/nested-smoke.sh" <<'EOF'
set -e -o pipefail
inner() { slicer --url /home/ubuntu/nested-slicer/slicer.sock "$@"; }

# Bound the startup wait; if it fails, inspect bg logs from the workstation.
for attempt in $(seq 1 60); do
  inner info && break
  sleep 1
done
inner info || exit 1

INNER_VM=$(inner vm add nested --persistent=false --tag workflow=nested-smoke --json |
  jq -er '.hostname | select(type == "string" and length > 0)') || exit 1
inner vm ready "$INNER_VM" --timeout 5m
inner vm exec "$INNER_VM" -- 'uname -a && cat /etc/os-release'
inner vm health "$INNER_VM" --json
inner vm delete "$INNER_VM"
inner vm list
EOF
TEST_STATUS=0
slicer vm exec "$OUTER_VM" --uid 0 -- 'bash -se' < "$EVAL_DIR/nested-smoke.sh" || TEST_STATUS=$?
```

`TEST_STATUS` retains a failed lifecycle result while the workstation cleanup
below collects diagnostics and stops the inner daemon. Use `vm exec` for this
test; an interactive `vm shell` session is not a test exit-status interface.
Smoke-test VMs are ephemeral, so successful daemon
shutdown also removes VMs and disks left by failed tests.

For project E2E tests, point the test harness at this same inner socket and run
it inside the outer VM with socket access. Assert the expected lifecycle and
workload results, retain logs/reports, and propagate the test process's exit
status. Use [bg-exec.md](bg-exec.md) for long test runs. For guest-agent version
tests, also follow [daemon-setup.md](daemon-setup.md#verify-a-newly-published-guest-agent)
so a cached image does not mask the version under test.

## Access and cleanup

Native shell/exec/copy through each daemon works without workstation routes to
the inner subnet. Run network assertions from the outer VM when possible.
For direct LAN access to inner VMs, follow the official guide's
[routing instructions](https://docs.slicervm.com/tasks/nested-virtualization/#routing-to-nested-vms-over-the-lan),
substituting actual subnets and gateways. Those Linux bridge routes are not a
drop-in configuration for Mac VMNet; prefer native commands or explicit port
forwarding there.

From the **workstation**, save test artifacts and daemon logs before teardown:

```bash
slicer vm bg logs "$OUTER_VM" "$INNER_EXEC" > "$EVAL_DIR/daemon.log" || echo 'Could not save daemon logs.' >&2
# Copy project-specific reports out with slicer vm cp before deleting the VM.
slicer vm bg kill "$OUTER_VM" "$INNER_EXEC" --signal TERM --grace 180s || echo 'Stop request failed; checking process status.' >&2
WAIT_STATUS=0
slicer vm bg wait "$OUTER_VM" "$INNER_EXEC" --timeout 3m --json > "$EVAL_DIR/shutdown.json" || WAIT_STATUS=$?
# Capture again after waiting, including shutdown output, before reaping.
slicer vm bg logs "$OUTER_VM" "$INNER_EXEC" > "$EVAL_DIR/shutdown.log" || echo 'Could not save shutdown logs.' >&2
if [ "$WAIT_STATUS" -ne 0 ] || ! jq -e '.running == false and .timed_out == false' "$EVAL_DIR/shutdown.json" >/dev/null; then
  echo 'Cannot confirm shutdown; retain the VM and background record for inspection.' >&2
  exit 1
fi
slicer vm exec "$OUTER_VM" --uid 0 --shell "" -- rm -f -- "$INNER_LICENSE" || exit $?
unset INNER_LICENSE
if ! jq -e '.exit_code == 0' "$EVAL_DIR/shutdown.json" >/dev/null; then
  echo 'Daemon exited unsuccessfully; license removed, VM and background record retained.' >&2
  exit 1
fi
slicer vm bg remove "$OUTER_VM" "$INNER_EXEC" || exit $?
if [ "${OUTER_CREATED:-false}" = true ]; then
  slicer vm delete "$OUTER_VM" || exit $?
  unset OUTER_VM OUTER_CREATED
fi
exit "${TEST_STATUS:-1}"
```

Delete the outer VM only when it was dedicated to this test and its results
have been collected. If it was reused for ongoing work, stop only the inner
daemon and retain the outer VM. On failures, collect logs before cleanup too;
avoid broad process kills or image-cache wipes on the outer host.
If setup or teardown is interrupted, remove the recorded temporary license with
the same `vm exec ... rm` command once the inner daemon is stopped, before
handing the retained VM to another workload.
Local scripts, logs, and shutdown status remain in `EVAL_DIR` for inspection;
remove that directory once the results are no longer needed.
