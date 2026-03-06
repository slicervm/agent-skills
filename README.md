# Slicer Agent Skills

[Agent Skills](https://agentskills.io/) for [Slicer](https://slicervm.com) — instant Linux microVMs powered by Firecracker.

Teach your AI coding agent how to launch, manage, and work with Slicer microVMs for sandboxed builds, E2E tests, Docker workflows, CI, and isolated dev environments.

## Available Skills

### use-slicer

`skills/use-slicer`

Comprehensive skill covering the full Slicer workflow — connecting to daemons (macOS, Linux, hosted box), creating VMs, running commands, copying files, port forwarding, agent sandboxes, and more.

Works from macOS (via slicer-mac) and Linux hosts.

## Installation

### npx (recommended — works with 40+ agents)

```bash
npx skills add slicervm/agent-skills
```

This installs the skill into whichever AI coding agents you have (Claude Code, Amp, Cursor, Codex, Gemini CLI, etc.).

### Claude Code Plugin

```bash
/plugin marketplace add slicervm/agent-skills
/plugin install use-slicer@slicer
```

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
