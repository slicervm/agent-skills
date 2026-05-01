---
name: use-k3sup
description: Provision K3s clusters with k3sup and k3sup-pro. Use when installing Kubernetes, creating single-node or HA k3s clusters, or wiring Slicer/remote VMs over SSH.
license: MIT
compatibility: Requires Bash and network access for installing k3sup/kubectl; Slicer VM workflows require the Slicer CLI and a running daemon.
---

# Use K3sup with Slicer VMs

Use this skill when the user asks for:
- install Kubernetes
- install k3s / create k3s cluster
- run k3sup or k3sup-pro
- provision single-node K3s or HA k3s with multiple slicer VMs

## Golden rules for agent behavior

- Prefer native Slicer commands (`slicer vm exec`, `slicer vm shell`, `slicer vm cp`) over SSH when the VM is local.
- For long or interactive terminal workflows, use `slicer vm shell` once and keep state there.
- Never run cluster bootstrap logic in userdata that blocks (cluster install/ready/token/join/proxy/port-forward). Use userdata for base package installs only.
- For slicer VM workflows, prefer the normal default user shell (implicit UID) and run privileged commands with passwordless `sudo`; do not default to root shells (`--uid 0`) unless explicitly requested.
- For single-node local installs on a slicer VM: prefer `k3sup install --local` from that VM.
- For any remote install (`--host` / `--ip`), always make SSH identity explicit (`--ssh-key`) and run from your current host.
- For `k3sup-pro`, run from a host with SSH access to the target VMs, not inside the target VM.
- For API-launched slicer VMs that need SSH, pass identity at launch with `--ssh-key` using a raw public key string (from `$(cat ~/.ssh/id_ed25519.pub)`), or use `--import-user` to import keys by GitHub username.
- On slicer-mac, do not target or reuse `slicer-1` unless the user explicitly requests it.
- On slicer-mac, any new API-launched VM must be created in the `sbox` host group (for example, `slicer vm add sbox ...`).

### Tool installation strategy (preferred)

- On the host machine (outside a VM), always install CLI tooling through `arkade` first:

```bash
curl -SLs https://get.arkade.dev | bash
# If command write permissions are restricted, run with sudo:
curl -SLs https://get.arkade.dev | sudo bash

arkade get k3sup
arkade get kubectl
```

- On Slicer VMs, `arkade` is preinstalled by default, so use it directly:

```bash
arkade get k3sup
arkade get kubectl
```

- If `k3sup` or `kubectl` is not present, install them from `arkade` rather than downloading release archives manually.
- For HA cluster operations with `k3sup-pro`, start by installing `k3sup-pro` with `k3sup get pro` from the control host (not from target nodes).

## Authoritative command map (from `--help`)

```bash
k3sup --help
```

### `k3sup` commands

- `completion`
- `get` (download helpers)
- `get-config`
- `install`
- `join`
- `node-token`
- `plan`
- `pro`
- `ready`
- `update`
- `version`
- `help`

### `k3sup pro` helper path

```bash
k3sup get pro --help
k3sup get pro
```

`k3sup get pro` installs `k3sup-pro`.

- default install path: `/usr/local/bin/`
- flags: `--path`, `--version`, `--help`

Important: `k3sup-pro` is typically used from your workstation or control host over SSH to slicer-hosted VMs.

## Key flags: `k3sup`

```bash
k3sup install --help
k3sup join --help
k3sup plan --help
k3sup get-config --help
k3sup node-token --help
k3sup ready --help
k3sup version --help
```

`k3sup install`
- `--local`
- `--host` / `--ip`
- `--user` (default `root`)
- `--ssh-key`
- `--ssh-port`
- `--k3s-channel`, `--k3s-version`
- `--cluster`
- `--token` (HA datastore token)
- `--datastore`
- `--k3s-extra-args`
- `--ipsec`
- `--tls-san`
- `--no-extras`
- `--merge`
- `--local-path`
- `--context`
- `--skip-install`
- `--print-command`
- `--sudo`

`k3sup join`
- `--host` / `--ip`
- `--user`
- `--server-host` / `--server-ip`
- `--server-user`
- `--server-url`
- `--server`
- `--server-ssh-port`
- `--node-token` / `--node-token-path`
- `--server-data-dir`
- `--k3s-channel`, `--k3s-version`
- `--k3s-extra-args`
- `--no-extras`
- `--skip-install`
- `--print-command`

`k3sup plan`
- positional argument: `hosts.json`
- `--servers`
- `--limit`
- `--user`
- `--ssh-key`
- `--context`
- `--merge`
- `--local-path`
- `--agent-k3s-extra-args`
- `--server-k3s-extra-args`
- `--tls-san`
- `--k3s-channel`, `--k3s-version`

`k3sup get-config`
- `--local`
- `--host` / `--ip`
- `--user`
- `--ssh-key`
- `--ssh-port`
- `--local-path`
- `--context`
- `--merge`
- `--print-command`
- `--sudo`

`k3sup node-token`
- `--host` / `--ip`
- `--user`
- `--local`
- `--ssh-key`
- `--ssh-port`
- `--server-data-dir`
- `--print-command`
- `--sudo`

`k3sup ready`
- `--kubeconfig`
- `--context`
- `--attempts`
- `--pause`
- `--quiet`

`k3sup update`
- prints update instructions for local binary migration.

## Key flags: `k3sup-pro`

```bash
k3sup-pro --help
k3sup-pro plan --help
k3sup-pro apply --help
k3sup-pro install --help
k3sup-pro join --help
k3sup-pro get-config --help
k3sup-pro node-token --help
k3sup-pro exec --help
k3sup-pro activate --help
k3sup-pro ready --help
k3sup-pro uninstall --help
k3sup-pro version --help
```

`k3sup-pro plan`
- positional args: `devices1.json devices2.json ...`
- `--servers`
- `--limit`
- `--user`
- `--ssh-key`
- `--ssh-port`
- `--parallel`
- `--output` (table/json/yaml)
- `--plan-file`
- `--datastore`
- `--token`
- `--context`
- `--local-path`
- `--server-extra-args`
- `--agent-extra-args`
- `--label` / `--server-label` / `--agent-label`
- `--tls-san`
- `--k3s-channel`, `--k3s-version`
- `--ipsec`
- `--svclb`
- `--traefik`
- `--update`
- `--dry-run`
- `--verbose`

`k3sup-pro apply`
- positional arg: `plan-file` (default `plan.yaml`)
- `--dry-run`
- `--force`
- `--predownload`
- `--print-command`
- `--update`
- `--verbose`

`--servers` and `--user` are plan-only flags for `k3sup-pro`; do not pass them to `k3sup-pro apply`.

Note: `k3sup-pro apply` uses SSH settings from the plan file (`user`, `ssh_key`, `ssh_port`) and should still succeed even when the terminal SSH agent has no keys, as long as the plan includes `--ssh-key`.

If `apply` still reports `handshake failed: unable to authenticate [none publickey]`:
- confirm the plan contains the correct `ssh_key` path and username for the target host;
- verify passwordless SSH access for that key directly: `ssh -i <key> <user>@<ip> 'echo ok'`;
- if needed, run plan/apply inside an SSH agent-backed shell or run with `SSH_AUTH_SOCK=`.

`k3sup-pro install`
- same install flags as `k3sup install`, plus `--cluster` for embedded etcd flow.

`k3sup-pro join`
- same as `k3sup join`.

`k3sup-pro get-config`
- positional args: `devices*.json` or `plan.yaml`
- `--local`
- `--host` / `--ip`
- `--user`
- `--ssh-key`
- `--ssh-port`
- `--context`
- `--local-path`
- `--merge`
- `--print-command`
- `--sudo`

`k3sup-pro node-token`
- same as `k3sup node-token` plus plan/host driven flows via args.

`k3sup-pro exec`
- positional args: `plan.yaml` or `devices*.json`
- command argument at the end
- `--servers` / `--agents`
- `--parallel`
- `--user`
- `--ssh-key`
- `--ssh-port`
- `--verbose`

`k3sup-pro activate`
- `--access-token` to activate subscription/license.

`k3sup-pro ready`
- same key flags as `k3sup ready`.

`k3sup-pro uninstall`
- positional args: `devices*.json` or `plan.yaml`
- `--parallel`
- `--user`
- `--ssh-key`
- `--ssh-port`
- `--dry-run`
- `--verbose`

## Recommended workflows

Single-node on a Slicer VM (in-VM path)

1. Create or reuse a workflow-tagged VM and inject any required SSH key if needed.
2. Inside the VM shell or exec:

```bash
k3sup install --local --k3s-version v1.31.2+k3s1 --context default
k3sup get-config --local --local-path kubeconfig
k3sup ready
```

Remote VM using SSH from host

1. Ensure VM has SSH key in place at launch time:

```bash
slicer vm add sbox --tag workflow=k3s \
  --ssh-key "$(cat ~/.ssh/id_ed25519.pub)"
```

2. From the host:

```bash
k3sup install --host <VM_IP> --user ubuntu --ssh-key ~/.ssh/id_ed25519
k3sup get-config --host <VM_IP> --user ubuntu --ssh-key ~/.ssh/id_ed25519
k3sup ready --kubeconfig kubeconfig
```

HA cluster with k3sup-pro

1. Build or collect a hosts file (JSON):

```json
[
  {"hostname": "node-1", "ip": "192.168.128.102"},
  {"hostname": "node-2", "ip": "192.168.128.103"},
  {"hostname": "node-3", "ip": "192.168.128.104"}
]
```

2. On a machine with SSH to all nodes:

```bash
k3sup get pro
k3sup-pro plan devices.json --servers 3 --user ubuntu --ssh-key ~/.ssh/id_ed25519 > plan.yaml
k3sup-pro apply plan.yaml
k3sup-pro get-config plan.yaml --user ubuntu --ssh-key ~/.ssh/id_ed25519
k3sup-pro ready --kubeconfig ./kubeconfig
```

On slicer-mac, if `k3sup-pro` is needed and only one VM is available, use a single-entry devices file derived from `slicer vm list --json`:

```bash
slicer vm list --json | jq 'map({hostname, ip})' > devices.json
k3sup get pro
k3sup-pro plan devices.json --servers 1 --user ubuntu --ssh-key ~/.ssh/id_ed25519 > plan.yaml
k3sup-pro apply plan.yaml
```

On environments where `k3sup-pro` still fails with `handshake failed: unable to authenticate [none publickey]`, run under an SSH agent-backed session and try again:

```bash
ssh-agent bash -c '
  ssh-add ~/.ssh/id_ed25519
  k3sup-pro plan devices.json --servers 1 --user ubuntu --output yaml > /tmp/plan.yaml
  k3sup-pro apply /tmp/plan.yaml
'
```

If it still fails with the same handshake error, verify host key auth first:

```bash
ssh -vvv -i ~/.ssh/id_ed25519 -o PreferredAuthentications=publickey ubuntu@<VM_IP> 'echo ok'
```

`k3sup-pro` requires a valid license context for `plan/apply`. If `k3sup-pro` returns:

`invalid license, error: JWT parse error: token has invalid claims: token is expired`

refresh licensing first:

```bash
k3sup-pro activate --access-token /path/to/access-token
```

Then rerun `k3sup-pro plan ...` and `k3sup-pro apply ...`.

`k3sup-pro` should not be launched from inside target VMs; it orchestrates SSH sessions and should run from the control host.
