---
name: use-slicer
description: Use Slicer to launch Linux microVMs for sandboxed builds, E2E tests, Docker, CI, and isolated dev environments — works from macOS and Linux hosts
license: MIT
compatibility: Requires Bash, the Slicer CLI, and access to a running Slicer daemon or slicer-mac.
---

# Use Slicer — Launch Linux MicroVMs

Slicer gives you instant Linux microVMs powered by Firecracker. Use it when you need a real Linux environment with systemd, internet access, SSH, Docker/container workflows, k3s tests, isolated CI/E2E runs, or a disposable VM for coding-agent work.

VMs boot in 1-3 seconds. Prefer native Slicer commands over SSH unless the task explicitly requires SSH/SCP.

Docs: https://docs.slicervm.com
Go SDK: https://github.com/slicervm/sdk

## Load More Detail When Needed

- Daemon setup, slicer-mac, Slicer Box, Linux/remote connection, config generation, custom images, secrets, disks, utility commands, and troubleshooting: see [references/daemon-setup.md](references/daemon-setup.md) and [references/workflows-and-admin.md](references/workflows-and-admin.md).
- VM creation, command execution, background exec, file copy, port forwarding, lifecycle, and monitoring: see [references/vm-operations.md](references/vm-operations.md).
- Long-running background commands: see [references/bg-exec.md](references/bg-exec.md).
- Bridge/isolated networking and port-forwarding details: see [references/networking.md](references/networking.md).
- Coding-agent sandboxes in VMs: see [references/agent-sandboxes.md](references/agent-sandboxes.md).

## Core Workflow

For agent tasks that can create infrastructure, use this default pattern:

1. Reuse the session VM when already known. Otherwise create one VM, tag it, wait for readiness, and keep using that same VM for the turn.
2. Tag VMs with a workflow label, for example `workflow=<slug>`, so they can be rediscovered later.
3. Use `slicer vm exec` for short bounded commands, `slicer vm bg exec` for long-running processes, `slicer vm shell` for interactive sessions, and `slicer vm cp`/`slicer cp -r` for file transfer.
4. On slicer-mac, create API-launched disposable VMs in the `sbox` host group. Do not target or reuse `slicer-1` unless the user explicitly asks for the persistent Linux twin.
5. Run `slicer vm ready <VM_NAME>` after creation before executing workload commands.
6. Clean up disposable VMs when the task no longer needs them, unless the user requested persistence.

```bash
WORKFLOW=ci-$(date +%Y%m%d-%H%M%S)
if [ -n "${SLICER_SESSION_VM:-}" ]; then
  VM_NAME="$SLICER_SESSION_VM"
else
  VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
  slicer vm ready "$VM_NAME"
  export SLICER_SESSION_VM="$VM_NAME"
fi

slicer vm exec "$VM_NAME" --uid 1000 -- "uname -a"
```

## Connect To Slicer

Slicer requires a running daemon.

- macOS with slicer-mac: no `--url` is usually needed; the socket is auto-detected at `~/slicer-mac/slicer.sock`.
- Slicer Box: use `SLICER_URL=https://box.slicervm.com` and the user-provided token file.
- Existing local or remote Linux daemon: ask the user for the URL and token path; do not guess secrets.
- New local Linux daemon: check for existing Slicer/firecracker processes and CIDR conflicts before starting another daemon.

Connectivity check:

```bash
slicer info --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```

Every `slicer vm` subcommand accepts `--url` and `--token-file` or `--token`.

## VM Basics

```bash
slicer vm list
slicer vm group
slicer vm add sbox --tag workflow=<slug>
slicer vm ready VM_NAME --agent --timeout 5m
slicer vm health VM_NAME --json
```

Use `--json` when parsing output. The host group argument may be optional on single-group deployments; when multiple host groups exist, specify one explicitly.

For persistent disposable sandboxes, pair `--persistent` with tags:

```bash
VM_NAME=$(slicer vm add sbox --persistent --tag workflow=rustfs --tag purpose=s3-demo | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm list --json | jq -r '.[] | select(.tags.workflow=="rustfs") | .hostname'
```

## Commands In VMs

Foreground commands:

```bash
slicer vm exec VM_NAME --uid 1000 -- "sudo apt update && sudo apt install -y nginx"
slicer vm exec VM_NAME --uid 1000 --cwd ~/project --env FOO=bar -- "env | sort | head -n 5"
```

`slicer vm exec` defaults to shell execution. Use `--shell ""` only when you intentionally want direct exec with no shell interpretation.

Interactive sessions:

```bash
slicer vm shell VM_NAME --uid 1000
```

Long-running commands:

```bash
EX=$(slicer vm bg exec VM_NAME --uid 1000 --cwd /home/ubuntu/app -- npm run dev \
     | awk -F'[= ]' '/exec_id=/ {for (i=1;i<=NF;i++) if ($i=="exec_id") print $(i+1)}')
slicer vm bg logs VM_NAME "$EX"
slicer vm bg kill VM_NAME "$EX"
slicer vm bg remove VM_NAME "$EX"
```

`bg exec` defaults to direct exec, unlike `vm exec`. Pass binary and args as separate tokens, or opt into a shell with `--shell=/bin/bash`.

## File Transfer

```bash
slicer vm cp ./local-file.txt VM_NAME:/tmp/file.txt --uid 1000
slicer vm cp VM_NAME:/etc/os-release ./os-release.txt
slicer cp -r ./my-project/ VM_NAME:/home/ubuntu/project/ --uid 1000 \
  --exclude '**/.git/**' --exclude '**/node_modules/**'
```

Add a `.slicerignore` at the copied directory root to skip build outputs, dependency caches, and large artifacts.

## Port Forwarding

Use `slicer vm forward` with SSH-style `-L` mappings. Check that the local port is free first.

```bash
slicer vm forward VM_NAME -L 8080:127.0.0.1:8080
slicer vm forward VM_NAME -L /tmp/docker.sock:/var/run/docker.sock
slicer vm forward VM_NAME -L 2222:127.0.0.1:22
```

Port forwards run in the foreground; background them with `&` when needed. Use high host ports for privileged VM services unless the user asks otherwise.

## Common Patterns

- E2E isolation: create tagged VM, copy project, run tests, copy results back, delete VM.
- Remote Docker from macOS: forward `/var/run/docker.sock`, set `DOCKER_HOST=unix:///tmp/docker.sock`, then run Docker locally while containers execute in the VM.
- Linux build from macOS: copy project into a VM, build there, copy the artifact back.
- Quick k3s: install CLIs with `arkade`, install k3s, forward 6443, copy kubeconfig, run `kubectl` from the host.
- Database testing: install DB in VM, forward the database port, connect from host.
- SSH/SCP: forward VM port 22 only when external tooling requires SSH; otherwise prefer `slicer vm exec` and `slicer vm cp`.

## Guardrails

- Do not put blocking calls, port forwards, or interactive sessions in `userdata`; keep userdata non-interactive and short-lived.
- Avoid `slicer vm exec ... &`; use `slicer vm bg exec` for reconnectable long-running work.
- Do not infer local token paths for remote endpoints. Use explicit user-provided credentials.
- On Linux, check for CIDR and host group conflicts before starting another Slicer daemon.
- Use `slicer vm add --help`, `slicer vm exec --help`, or the relevant help output if flag support is uncertain.
