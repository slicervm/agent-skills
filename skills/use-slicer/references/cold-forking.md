# Cold Forking Prepared VMs

Cold forking commits the disk of a stopped, persistent builder VM, then starts
clean children from that immutable disk state. Use it when setup is expensive
or every job should start from the same known state.

## Requirements and boundaries

Cold forking requires a stopped, persistent source VM. The backend-specific
boundaries are:

- Linux uses Firecracker with `image`, `devmapper`, or `zfs` storage. Bridge
  and isolated networking are supported.
- Slicer for Mac uses APFS copy-on-write disk clones and supports the `sbox`
  host group only.

Cold forking is different from suspend/restore: only disk state is reused;
processes, sockets, and RAM are not.

On Linux, bridge-mode forks inherit their host-group networking. Per-fork
`--allow`, `--no-allow`, and `--drop` rules require isolated networking.
Slicer for Mac uses Apple VZ networking, and its allow/drop configuration
applies to every VM in the `sbox` host group. It rejects per-fork network
overrides. Use separate Slicer Proxy clients to distinguish a hot builder from
a restricted runner.

## Terms

- **Builder**: the original persistent VM which performs setup and is committed.
- **Runner**: an allocator-named child forked from the commit.
- **Cache key**: a caller-owned key which maps reusable setup inputs to a commit.

Never choose a runner hostname. `slicer vm fork` accepts one positional value,
the commit ID, and returns the allocated hostname. Use tags for job, tenant, or
workflow identity.

## Agent-safe workflow

Use JSON for every value consumed by automation. Pick a host group which
supports cold forks (`sbox` on macOS), then look for a cached builder before
doing any setup:

```bash
# Slicer for Mac. On Linux, replace this with an existing Firecracker group.
GROUP=sbox
WORKFLOW=cold-fork-arkade
CACHE_KEY=arkade-go-v1

COMMIT=$(slicer vm commit list \
  --cache-key "$CACHE_KEY" \
  --json | jq -r '.[0].commit_id // empty')
```

On a cache miss, launch and prepare a persistent builder. Give every VM a
descriptive tag:

```bash
if [ -z "$COMMIT" ]; then
  BUILDER=$(slicer vm add "$GROUP" \
    --persistent \
    --tag "workflow=$WORKFLOW" \
    --tag role=builder \
    --wait \
    --json | jq -r '.hostname')

  slicer vm exec "$BUILDER" -- \
    "sudo arkade system install go"

  slicer vm exec "$BUILDER" -- \
    "git clone https://github.com/alexellis/arkade /home/ubuntu/arkade && \
     cd /home/ubuntu/arkade && \
     /usr/local/go/bin/go build -mod=vendor -o ./arkade"

  slicer vm shutdown "$BUILDER"
  COMMIT=$(slicer vm commit "$BUILDER" \
    --cache-key "$CACHE_KEY" \
    --tag "workflow=$WORKFLOW" \
    --json | jq -r '.commit_id')
fi
```

The cache is for the complete committed disk, not individual layers. The
caller owns invalidation: include the base image, toolchain, setup-script, or
lock-file version in the key, and change it when those inputs change.

On a hit, skip the whole builder block and fork immediately:

```bash
RUNNER=$(slicer vm fork "$COMMIT" \
  --tag "workflow=$WORKFLOW" \
  --tag role=runner \
  --json | jq -r '.hostname')

slicer vm exec "$RUNNER" -- "hostname && cat /etc/machine-id"
```

Each child receives its own allocated hostname, IP/MAC identity, guest
hostname, and machine ID. Minimal Slicer images do not contain SSH keys, so do
not use SSH host-key presence as a generic identity check.

## Fork with no egress

On Linux, only use these flags with an isolated host group:

```bash
RUNNER=$(slicer vm fork "$COMMIT" \
  --tag "workflow=$WORKFLOW" \
  --tag role=closed-runner \
  --no-allow \
  --drop 0.0.0.0/0 \
  --json | jq -r '.hostname')
```

The DROP is applied outside the guest. For partial access, replace the empty
allow list with explicit `--allow` entries, such as an inference server on the
LAN. For path, method, credential, and TTL controls, use the companion
`use-slicer-proxy` skill.

On macOS, first configure the whole `sbox` host group so Slicer Proxy is its
only egress path. Use this order instead of the generic builder preparation
above:

```bash
BUILDER=$(slicer vm add sbox \
  --persistent \
  --tag "workflow=$WORKFLOW" \
  --tag role=builder \
  --wait \
  --json | jq -r '.hostname')

HOT_CLIENT="builder-$BUILDER"
HOT_TOKEN=$(slicer proxy client create "$HOT_CLIENT")
slicer proxy allow "$HOT_CLIENT" --host '*'

slicer vm exec \
  --uid 0 \
  --env HTTP_PROXY="http://:$HOT_TOKEN@192.168.64.1:3128" \
  --env HTTPS_PROXY="https://proxy:$HOT_TOKEN@192.168.64.1:3129" \
  "$BUILDER" -- "arkade system install go"

slicer proxy client delete "$HOT_CLIENT"
slicer vm shutdown "$BUILDER"
COMMIT=$(slicer vm commit "$BUILDER" \
  --cache-key "$CACHE_KEY" \
  --tag "workflow=$WORKFLOW" \
  --json | jq -r '.commit_id')

RUNNER=$(slicer vm fork "$COMMIT" \
  --tag "workflow=$WORKFLOW" \
  --tag role=runner \
  --wait \
  --json | jq -r '.hostname')

COLD_CLIENT="runner-$RUNNER"
COLD_TOKEN=$(slicer proxy client create "$COLD_CLIENT")
# No runner rules means default-deny; add only required destinations.
```

Pass `HOT_TOKEN` only as an environment value while preparing the builder.
Do not install it into the builder disk before committing, because every fork
inherits that disk. Delete the hot client when preparation finishes. Give the
fork `COLD_TOKEN` after launch, either per command or through the guest proxy
helper. A client with no allow rules is fully denied; a client with a small
rule set is a restricted profile. Use a unique client per VM so audit,
revocation, and policy remain isolated. The host-group firewall remains the
same for every `sbox` VM—the client token selects policy at Slicer Proxy.

Do not store reusable credentials or confidential inputs in the builder. Copy
them into the runner after the fork, or keep them on the host and inject
short-lived access through Slicer Proxy.

## Concurrent platform workflows

The daemon serialises commits which use the same cache key and rejects a
different commit trying to claim an existing key. It does not prevent two
callers from both performing builder setup after a simultaneous cache miss.
Coordinate the initial build in the platform, then let all jobs reuse the
winning commit.

Forks can run concurrently. Capture each JSON response independently and use
its `.hostname`; do not infer names or scan `vm list` for the newest VM.

## Cleanup

Runners are persistent and must be deleted explicitly:

```bash
slicer vm delete "$RUNNER"
```

The commit remains reusable. To remove the complete library entry, delete all
forked children, delete the stopped source builder, then delete the commit:

```bash
SOURCE=$(slicer vm commit list \
  --cache-key "$CACHE_KEY" \
  --json | jq -r '.[0].source_hostname')
slicer vm delete "$SOURCE"
slicer vm commit delete "$COMMIT"
```

Deleting a commit while its source or children still depend on it is rejected.

## Existing Linux installations

For the initial cold-forking release, refresh both the binary and locally
cached guest images before testing:

```bash
sudo slicer update
sudo slicer image wipe
```

Run the daemon from a fresh project directory, or remove stale `.lock` files
from the existing project, so the updated guest agent is used. Do not delete
disk images which contain data the user wants to keep.
