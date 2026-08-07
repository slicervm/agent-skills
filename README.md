# Slicer Agent Skills

[Agent Skills](https://agentskills.io/) for [Slicer](https://slicervm.com) — instant Linux microVMs powered by Firecracker.

Teach your AI coding agent how to launch, manage, and work with Slicer microVMs for sandboxed builds, E2E tests, Docker workflows, CI, and isolated dev environments.

## Available Skills

### use-slicer

`skills/use-slicer`

Comprehensive skill covering the full Slicer workflow — connecting to daemons
(macOS, Linux, hosted box), creating and naming VMs, managing mutable tags,
cold forking prepared builders, running commands, copying files, port
forwarding, agent sandboxes, and more.

Works from macOS (via slicer-mac) and Linux hosts.

### use-slicer-worktrees

`skills/use-slicer-worktrees`

Move a git worktree or repository into a Slicer microVM with a working, self-contained `.git`. Prefer agent `--worktree` mode for coding sandboxes; use `slicer wt push` / `pull` / `list` for lower-level VM flows. Pull commits back onto your host branch when the VM work is done.

### use-slicer-proxy

`skills/use-slicer-proxy`

Filter, audit, and inject secrets into HTTP(S) egress from Slicer microVMs with Slicer Proxy. Covers default-deny allow rules (host / path / method / port / TTL), credential injection (Bearer, Basic, and OAuth for Claude/Codex/Copilot/xAI), audit mode for path discovery, and TCP passthrough — on both Linux and macOS.

### use-s3-rustfs

`skills/use-s3-rustfs`

Install and run [RustFS](https://rustfs.com) (S3-compatible object storage in Rust) inside a Slicer VM, and talk to it from boto3, aws-cli, or `mc`. Covers the non-interactive installer invocation, default credentials/ports, and common client pitfalls (path-style vs virtual-host, SigV4 region quirks).

### use-k3sup

`skills/use-k3sup`

Single-node and HA K3s provisioning with `k3sup` / `k3sup-pro`, using either:
- local in-VM install (`k3sup install --local`)
- remote install from your machine (`--host` / `--user`, typically `ubuntu`)
- Slicer VM flows and SSH setup for API-launched guests

## Installation

### npx (recommended — works with 40+ agents)

```bash
npx skills add slicervm/agent-skills
```

This installs the skills into whichever AI coding agents you have (Claude Code, Amp, Cursor, Codex, Gemini CLI, etc.).

### Claude Code Plugin

```bash
/plugin marketplace add slicervm/agent-skills
/plugin install use-slicer@slicer
/plugin install use-slicer-worktrees@slicer
/plugin install use-slicer-proxy@slicer
/plugin install use-s3-rustfs@slicer
/plugin install use-k3sup@slicer
```

Install only the plugin skills you need; `use-s3-rustfs`, `use-slicer-worktrees`, and `use-slicer-proxy` all assume `use-slicer` is also installed.
Claude Code exposes plugin skills under their plugin namespace, for example `/use-slicer:use-slicer`.

### Manual

Clone and copy the skill into your agent's skills directory:

```bash
git clone https://github.com/slicervm/agent-skills.git
cp -r agent-skills/skills/use-slicer .claude/skills/   # Claude Code
cp -r agent-skills/skills/use-slicer .agents/skills/    # Amp / Codex
cp -r agent-skills/skills/use-slicer .cursor/skills/    # Cursor
```

## Example Prompts

```
Launch a Slicer VM and run my test suite inside it
```

```
Forward Docker from my Slicer VM so I can build containers locally
```

```
Set up a k3s cluster in a Slicer VM
```

```
Copy my project into a VM, build it, and bring back the binary
```

```
Launch a Codex sandbox with my git worktree
```

```
Lock down a VM's egress so it can only reach the npm registry
```

```
Prepare one builder VM, cache it, then fork a clean runner for each job
```

## What is Slicer?

Slicer turns a Linux host into a private microVM cloud. VMs boot in 1–3 seconds with full systemd, internet access, and SSH. It targets:

- Sandboxed code execution and CI runners
- Preview environments and AI agent sandboxes
- Docker/container workflows with port forwarding
- Kubernetes (k3s) clusters for testing
- GPU/PCI passthrough workloads

**Website**: [slicervm.com](https://slicervm.com)
**Docs**: [docs.slicervm.com](https://docs.slicervm.com)
**Go SDK**: [github.com/slicervm/sdk](https://github.com/slicervm/sdk)

## License

MIT — see [LICENSE](LICENSE).
