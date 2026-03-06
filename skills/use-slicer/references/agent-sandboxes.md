# Agent Sandbox Reference

Slicer has built-in commands to launch coding agents inside isolated microVMs. Each command creates a VM, copies credentials + workspace, installs the agent, and attaches a session.

## Commands

| Command | Agent | Tags |
|---------|-------|------|
| `slicer amp [path]` | Amp | `agent`, `amp` |
| `slicer claude [path]` | Claude Code | `agent`, `claude` |
| `slicer codex [path]` | Codex | `agent`, `codex` |
| `slicer workspace [path]` | None (clean shell) | `workspace` |

## What happens on launch

1. Host group is selected (auto if only one, or `--hostgroup NAME`)
2. Fresh microVM is created
3. Waits for guest agent readiness
4. Credentials are copied into the VM:
   - **Amp**: `~/.local/share/amp/secrets.json`, `~/.config/amp/settings.json`
   - **Claude**: `~/.claude/.credentials.json`, `~/.claude/settings.json`, `~/.claude.json`
   - **Codex**: `~/.codex/auth.json`, `~/.codex/config.toml`
5. Workspace directory is copied (honouring `.slicerignore`)
6. Agent is installed via arkade
7. Session is attached

## Session modes (`--tmux`)

| Mode | Description |
|------|-------------|
| `local` (default) | tmux on the host, two panes connecting to VM via `slicer vm shell` |
| `remote` | tmux inside the VM, attached via `vm shell` |
| `none` | Direct exec, no tmux |

## Reattach to existing VM

Pass the VM name instead of a path:

```bash
slicer amp amp-1
slicer claude claude-1
slicer codex codex-1
slicer workspace workspace-1
```

## .slicerignore

Place at workspace root. Same syntax as `.gitignore`. Controls what gets copied into the VM.

```
# Example .slicerignore
node_modules/
.git/
dist/
target/
*.log
*.img
```

## Ctrl-C during setup

If you press Ctrl-C during the setup phase (before the agent starts), the VM is automatically deleted.

## Common flags

All agent commands share:

| Flag | Purpose |
|------|---------|
| `--hostgroup NAME` | Pick host group |
| `--uid N` | UID for copy/exec/shell (default: auto-detect) |
| `--timeout 5m` | Agent readiness timeout |
| `--tmux local\|remote\|none` | Session mode |
| `--tag key=value` | Metadata tags |
| `--url` / `--token-file` | API connection |
