# Memory Forking Running VMs

Memory forking, also called hot forking, checkpoints a running Firecracker VM
and creates children which resume its captured processes and memory. Use it
when process start-up, dependency loading, or in-memory preparation is the
expensive part of a workload.

## Choose cold or memory forking

| Property | Cold fork | Memory fork |
|---|---|---|
| Source at commit | Stopped, persistent VM | Running, ready VM |
| Captured state | Writable disks | RAM, VMM state, and writable disks |
| Child starts | Fresh boot | Resumes captured processes |
| Linux storage | `image`, `devmapper`, or `zfs` | `image` only |
| Linux networking | Bridge or isolated | Isolated only |
| Backends | Firecracker and Slicer for Mac disk clones | Firecracker on Linux amd64 |

Prefer a cold fork for arbitrary workloads or whenever a fresh boot is useful.
Use a memory fork for a deliberately prepared process which can wait at a
job-release barrier before receiving child-specific work.

## Requirements

A memory-fork source must have all of these properties:

- Linux amd64 host with Firecracker 1.17.0 or newer.
- Firecracker hypervisor, isolated networking, and `image` storage.
- A running VM whose guest agent is ready.
- A recent guest agent with the `memory-fork-finalize-v1` capability.
- The CPU and RAM shape needed by every child. Memory forks cannot resize it.

Memory forking is not currently available with Slicer for Mac, Apple VZ,
cloud-hypervisor, QEMU, bridge networking, devmapper, or ZFS. Use current
Slicer host and guest-agent versions; a source created from an older image may
need its guest agent updated before capture. Slicer detects its default
Firecracker version at daemon start, so restart the daemon after upgrading
Firecracker and before creating a memory commit.

## Prepare a safe source

The child receives new infrastructure and guest identity:

- private writable root and config disks;
- isolated network namespace and vsock endpoint;
- Slicer authority token;
- hostname, machine ID, and SSH host keys; and
- kernel entropy reseeded from the host.

The application memory is intentionally duplicated. That includes
application PRNG state, cached credentials, active external sessions,
background jobs, and other in-memory secrets. Before committing:

1. Finish installation and expensive process initialisation.
2. Leave the process idle at a well-defined job-release barrier.
3. Close live SSH, database, API, and other external sessions.
4. Plan to reinitialise application PRNG state after each fork.
5. Inject child-specific credentials and work only after the fork is ready.

Treat the memory snapshot as sensitive as the source VM. Do not publish or
share its files as a general-purpose image.

## Agent-safe CLI workflow

Use JSON for values consumed by automation and deterministic tags for later
inspection and cleanup. Start with a persistent source in an existing Linux
host group configured for isolated networking and `image` storage:

```bash
GROUP=forkdemo
WORKFLOW=memory-fork-build
RUN="memory-fork-$(date +%Y%m%d-%H%M%S)"
SOURCE_REF="$RUN-source"

SOURCE=$(slicer vm add "$GROUP" \
  --name "$SOURCE_REF" \
  --persistent \
  --wait \
  --tag "workflow=$WORKFLOW" \
  --tag "run=$RUN" \
  --tag role=memory-source \
  --json | jq -r '.hostname')
```

Prepare the workload in the source. A service, language runtime, model, or
coding tool may remain running, but it should be waiting for new work rather
than talking to external systems:

```bash
slicer vm cp ./prepare-source.sh "$SOURCE":/tmp/prepare-source.sh
slicer vm exec "$SOURCE" -- "chmod +x /tmp/prepare-source.sh && /tmp/prepare-source.sh"

# Example shape for a workload which deliberately waits for child-specific work.
slicer vm bg exec "$SOURCE" --uid 1000 --cwd /home/ubuntu/app -- \
  /home/ubuntu/app/bin/worker --wait-for-job
```

Capture the running source. `--memory` and `--mem` are shortcuts for
`--mode memory`:

```bash
CACHE_KEY=memory-fork-build-v1
COMMIT=$(slicer vm commit "$SOURCE" \
  --memory \
  --cache-key "$CACHE_KEY" \
  --tag "workflow=$WORKFLOW" \
  --tag "run=$RUN" \
  --json | jq -r '.commit_id')
```

The source is paused while Firecracker writes the checkpoint, then resumed.
The commit is immutable and reusable. Fork a child and let the default wait
cover agent readiness, identity personalisation, token rotation, and entropy
reseeding:

```bash
CHILD=$(slicer vm fork "$COMMIT" \
  --name "$RUN-child-1" \
  --tag "workflow=$WORKFLOW" \
  --tag "run=$RUN" \
  --tag role=memory-child \
  --json | jq -r '.hostname')

slicer vm exec "$CHILD" -- "hostname && cat /etc/machine-id"
```

The source and every child have independent writable disks. Reuse the same
commit for concurrent children and capture each JSON response separately; do
not infer allocator hostnames from list order.

## Asynchronous forks

The default `vm fork` waits until a memory child is ready to use. Prefer that
behaviour. `--no-wait` returns after the daemon accepts the fork, while the
child is still personalised and network-quarantined:

```bash
CHILD=$(slicer vm fork "$COMMIT" \
  --no-wait \
  --tag "workflow=$WORKFLOW" \
  --tag "run=$RUN" \
  --json | jq -r '.hostname')

slicer vm ready "$CHILD"
slicer vm exec "$CHILD" -- "hostname"
```

The acceptance time from `--no-wait` is not ready-to-use latency. If a caller
disconnects or times out after acceptance, the child may still exist. Find it
by its deterministic tags and delete it when appropriate.

## Suspend, restore, shutdown, and recommit

A memory-fork child can follow its own suspend and restore lifecycle:

```bash
slicer vm suspend "$CHILD"
slicer vm restore "$CHILD" --wait agent
```

This continues the same child from its saved RAM and process state. Repeating
suspend and restore is supported.

An ordinary shutdown of a persistent child followed by `slicer relaunch`
cold-boots that child's private disk; it does not resume the captured RAM.

A memory-fork child cannot currently become another reusable memory parent.
`slicer vm commit "$CHILD" --memory` returns `409 Conflict`. Reuse the original
commit, or prepare and commit an independent running VM when a new memory
template is needed.

## Firecracker version portability

Slicer records the Firecracker version in each snapshot and restores with that
exact version. When it differs from the daemon's current default, Slicer uses
`/usr/local/bin/firecracker-vVERSION`. If that binary is absent and the host
has internet access, Slicer fetches it with arkade, verifies the version, and
caches it at that path.

For offline restore, pre-populate the exact recorded version before restoring.
This compatibility path restores existing snapshots; it does not relax the
Firecracker 1.17.0 minimum for creating new memory commits.

## Go SDK

The Go SDK uses the same defaults. Omit `WithWait` to retain the default wait,
or request it explicitly for clarity:

```go
checkpoint, err := client.CommitVMWithOptions(ctx, sourceHostname,
	sdk.SlicerCommitVMOptions{Mode: "memory"})
if err != nil {
	return err
}

child, err := client.ForkCommittedVM(ctx, checkpoint.CommitID,
	sdk.WithWait(sdk.SlicerForkWaitAgent),
	sdk.WithTags("workflow=memory-fork-build", "role=memory-child"))
if err != nil {
	return err
}

fmt.Printf("child ready: %s\n", child.Hostname)
```

## Cleanup

Delete children before deleting the reusable commit. The running source is
independent of a memory commit, so keep it for later captures or delete it when
it is no longer needed:

```bash
slicer vm delete "$CHILD"
slicer vm commit delete "$COMMIT"
# Optional when the source is no longer useful:
slicer vm delete "$SOURCE"
```

Commit deletion is rejected while dependent children remain.

## Common failures

| Symptom | Meaning and action |
|---|---|
| `memory commit requires a running VM` | Restore or relaunch the intended source, then wait for its agent. |
| `memory commits initially require isolated networking and image storage` | Use a compatible host group; cold fork other storage or network modes. |
| `require Firecracker 1.17.0 or newer` | Upgrade Firecracker, restart Slicer, and retry with a VM using the new binary. |
| `guest agent does not support memory-fork...` | Update the source image or guest agent before capture. |
| Child reports `starting` | The fork used `--no-wait`; run `slicer vm ready CHILD` before agent operations. |
| `recapturing memory-fork children is not supported in this version` | Reuse the original commit or create a new source VM. |
| Exact Firecracker version cannot be prepared | Restore internet access for the verified download, or install the versioned binary for offline use. |
