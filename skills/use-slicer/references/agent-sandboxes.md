# Agent Sandbox Reference

Slicer has built-in commands to launch coding agents inside isolated microVMs. Each command creates a VM, installs the agent and its credentials, and — depending on the argument — optionally syncs a workspace and attaches a session.

## Commands

| Command | Agent | Tags |
|---------|-------|------|
| `slicer amp [path\|vm]` | Amp | `agent`, `amp` |
| `slicer claude [path\|vm]` | Claude Code | `agent`, `claude` |
| `slicer codex [path\|vm]` | Codex | `agent`, `codex` |
| `slicer copilot [path\|vm]` | GitHub Copilot CLI | `agent`, `copilot` |
| `slicer opencode [path\|vm]` | OpenCode | `agent`, `opencode` |
| `slicer workspace [path\|vm]` | None (clean shell) | `workspace` |

## Three ways to run

The single optional positional argument selects the mode:

| Argument | Mode | Behaviour |
|----------|------|-----------|
| *(none)* | provision-only | Create VM, sync git identity, copy credentials, install the agent — then stop. No workspace copy, no attach. |
| a local directory | workspace | As above, then copy the directory in (honours `.slicerignore`) and attach a session. |
| anything else | reattach | Treat as an existing VM name; wait for the agent and reattach. |

**Provision-only** (`slicer codex` with no argument) is the clean-VM mode. It does **not** copy the current directory — pass `.` explicitly for that. Provision-only VMs carry no workspace (`wd=`) tag. Get code into them with `slicer wt push` — see [Worktree workflow](#worktree-workflow-recommended-for-git-repos).

## What happens on launch

1. Host group is selected (auto if only one, or `--hostgroup NAME`)
2. Fresh microVM is created
3. Waits for guest agent readiness
4. Your git identity (`user.name` / `user.email`) and safe git preferences are synced in — never credentials or url rewrites
5. Agent credentials are copied into the VM:
   - **Amp**: `~/.local/share/amp/secrets.json`, `~/.config/amp/settings.json`
   - **Claude**: `~/.claude/.credentials.json`, `~/.claude/settings.json`, `~/.claude.json`
   - **Codex**: `~/.codex/auth.json`, `~/.codex/config.toml`
   - **Copilot**: `~/.config/github-copilot/apps.json`, `~/.copilot/config.json`
   - **OpenCode**: `~/.local/share/opencode/auth.json`, `~/.config/opencode/opencode.json`
6. *(workspace mode only)* the workspace directory is copied in and ownership fixed
7. The agent is installed via arkade
8. *(workspace / reattach modes)* a session is attached; *(provision-only)* a hint is printed and the command exits

## Session modes (`--tmux`)

| Mode | Description |
|------|-------------|
| `none` (default) | Direct exec, no tmux |
| `local` | tmux on the host, two panes connecting to the VM via `slicer vm shell` |
| `remote` | tmux inside the VM, attached via `vm shell` |

## Reattach to an existing VM

Pass the VM name instead of a path:

```bash
slicer amp amp-1
slicer claude claude-1
slicer codex codex-1
slicer copilot copilot-1
slicer opencode opencode-1
slicer workspace workspace-1
```

## Worktree workflow (recommended for git repos)

For a git project, prefer **provision-only + `slicer wt`** over copying the directory directly — it gives the VM a working, self-contained `.git` and a clean way to get commits back.

```bash
slicer codex                 # provision a clean codex VM (note the name it prints)
slicer wt push codex-1 .     # push the current worktree/repo into it
slicer codex codex-1         # attach; let the agent work and commit
slicer wt pull codex-1 .     # pull commits back — host branch fast-forwarded
git push                     # push from the host under your own identity
```

A plain copy of a git worktree breaks: its `.git` is a *file* holding an absolute host path, so every git command in the VM fails. `slicer wt` stages a sanitised `.git` instead. See the **`use-slicer-worktrees`** skill for the full `slicer wt push` / `pull` / `list` reference.

## .slicerignore

Place at workspace root. Same syntax as `.gitignore`. Controls what gets copied into the VM in workspace mode.

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
| `--tmux none\|local\|remote` | Session mode (default `none`) |
| `--tag key=value` | Metadata tags |
| `--url` / `--token-file` | API connection |
