# Agent Sandbox Reference

Slicer has built-in commands to launch coding agents inside isolated microVMs. Each command creates a VM, installs the agent and its credentials, and — depending on the argument or flags — optionally syncs a workspace or git worktree and attaches a session.

## Commands

| Command | Agent | Tags |
|---------|-------|------|
| `slicer amp [path\|vm]` | Amp | `agent`, `amp` |
| `slicer claude [path\|vm]` | Claude Code | `agent`, `claude` |
| `slicer codex [path\|vm]` | Codex | `agent`, `codex` |
| `slicer copilot [path\|vm]` | GitHub Copilot CLI | `agent`, `copilot` |
| `slicer opencode [path\|vm]` | OpenCode | `agent`, `opencode` |
| `slicer pi [path\|vm]` | Pi | `agent`, `pi` |
| `slicer workspace [path\|vm]` | None (clean shell) | `workspace` |

## Ways to run

The optional positional argument selects the base mode:

| Argument | Mode | Behaviour |
|----------|------|-----------|
| *(none)* | provision-only | Create VM, sync git identity, copy credentials, install the agent — then stop. No workspace copy, no attach. Mainly for advanced/manual flows. |
| a local directory | workspace | As above, then copy the directory in (honours `.slicerignore`) and attach a session. |
| anything else | reattach | Treat as an existing canonical hostname or friendly name; wait for the agent and reattach. |

For git repositories, prefer `--worktree` / `--wt` instead of creating a provision-only sandbox and then running `slicer wt push`. Worktree mode provisions the VM, pushes a self-contained `.git`, installs the agent into that path, and attaches in one command.

**Provision-only** (`slicer codex` with no argument) is the clean-VM mode. It does **not** copy the current directory — pass `.` explicitly for a workspace copy, or use `--worktree .` for a git repo.

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
   - **Pi**: `~/.pi/agent`
6. *(workspace mode only)* the workspace directory is copied in and ownership fixed; *(worktree mode only)* the git worktree is pushed with a self-contained `.git`
7. The agent is installed via arkade
8. *(workspace / worktree / reattach modes)* a session is attached; *(provision-only)* a hint is printed and the command exits

## Session modes (`--tmux`)

| Mode | Description |
|------|-------------|
| `none` (default) | Direct exec, no tmux |
| `local` | tmux on the host, two panes connecting to the VM via `slicer vm shell` |
| `remote` | tmux inside the VM, attached via `vm shell` |

## Reattach to an existing VM

Pass the canonical hostname or friendly name instead of a path:

```bash
slicer amp amp-1
slicer claude claude-1
slicer codex codex-1
slicer copilot copilot-1
slicer opencode opencode-1
slicer pi pi-1
slicer workspace workspace-1
```

Assign a friendly name when creating a sandbox, then use it for reattach and
other CLI commands:

```bash
slicer opencode --name papermaking
slicer opencode papermaking
slicer shell papermaking
```

`--name` is creation-time CLI sugar for the immutable `name=papermaking` tag.
Do not combine it with `--tag name=...`. See
[vm-names-and-tags.md](vm-names-and-tags.md) for the CLI/API boundary.

## Worktree workflow (recommended for git repos)

For a git project, prefer **`--worktree` mode** over copying the directory directly — it gives the VM a working, self-contained `.git` and a clean way to get commits back.

```bash
slicer codex --worktree .    # launch Codex with the current worktree
slicer wt pull codex-1 .     # pull commits back — host branch fast-forwarded
git push                     # push from the host under your own identity
```

Creating a provision-only agent sandbox first and then pushing into it still works, but treat that as an advanced/manual path when you deliberately need to stage code separately.

A plain copy of a git worktree breaks: its `.git` is a *file* holding an absolute host path, so every git command in the VM fails. `slicer wt` stages a sanitised `.git` instead. See the **`use-slicer-worktrees`** skill for the full `slicer wt push` / `pull` / `list` reference.

## Cold-forked agent bases

On a Linux Firecracker host, cold forking can prepare compilers, linters,
browsers, and agent binaries once, then create one runner per task. Do not put
reusable agent credentials, repository credentials, customer data, or untrusted
code into the committed builder: every child inherits its disk.

Prefer copying credentials and code into each runner after the fork, or keep
credentials on the host and use Slicer Proxy for narrowly scoped access. See
[cold-forking.md](cold-forking.md) for the builder/cache/fork workflow.

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
| `--name NAME` / `-n NAME` | Assign a unique friendly name when creating the VM |
| `--tag key=value` | Metadata tags |
| `--worktree` / `--wt` | Push a git worktree into the VM instead of tar-copying a directory |
| `--rm` | Make the VM ephemeral; sandboxes are persistent by default |
| `--url` / `--token-file` | API connection |
