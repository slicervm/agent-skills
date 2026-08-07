---
name: use-slicer-worktrees
description: Move a git worktree or repository into a Slicer microVM with a working, self-contained .git — prefer agent `--worktree` mode for coding sandboxes, use `slicer wt push` for manual VM flows, then pull commits back.
allowed-tools: Bash
---

# Slicer Worktrees — git worktrees and repos inside a microVM

For coding agent sandboxes, prefer `slicer <agent> --worktree [path]`: it launches the VM, pushes a git worktree with a **working, self-contained `.git`**, installs the agent into that path, and attaches in one command.

Use lower-level `slicer wt push` when you are working with a plain VM, reusing a separately created VM, or need explicit control over the push/pull lifecycle. The host repository is never mounted and its hooks never run inside the VM.

This skill assumes a running Slicer daemon — see the `use-slicer` skill for connecting to one.

## Why `slicer wt` (and not a plain copy)

A git **worktree**'s `.git` is a *file*, not a directory:

```
gitdir: /home/you/src/project/.git/worktrees/feature-x
```

That is an **absolute host path**. Tar-copying the worktree directory into a VM leaves the pointer dangling — every git command in the VM fails with `fatal: not a git repository`. And even for a normal repo, copying `.git` wholesale drags host hooks and config along.

Worktree mode and `slicer wt push` stage a fresh, sanitised `.git` instead, so git works correctly in the VM and the host repo stays untouchable.

## Quick start

```bash
slicer codex --worktree .     # launch a persistent Codex VM and push the current worktree in
# ...let the agent work and commit in the VM...
slicer wt pull <vm> .         # commits + files back, your branch fast-forwarded
git push                      # from the host, under your own identity
```

`<vm>` is the VM name printed by the agent command. Use `slicer amp`, `slicer claude`, `slicer copilot`, `slicer opencode`, `slicer pi`, or `slicer workspace` the same way. Use `--rm` when you want a disposable VM; worktree and agent sandboxes are persistent by default.

## Commands

| Command | Purpose |
|---------|---------|
| `slicer codex --worktree [path]` | Launch/provision Codex, push `path` as a git worktree, and attach |
| `slicer codex --wt [path]` | Alias for `--worktree` |
| `slicer workspace --worktree [path]` | Launch a clean shell VM with a pushed worktree and no coding agent |

The same `--worktree` / `--wt` flags are available on `slicer amp`, `slicer claude`, `slicer copilot`, `slicer opencode`, and `slicer pi`.

Lower-level worktree commands:

| Command | Purpose |
|---------|---------|
| `slicer wt push [vm] [path]` | Push the worktree at `path` into an existing VM |
| `slicer wt push --launch [path]` | Launch a fresh persistent VM, then push |
| `slicer wt pull <vm> [path]` | Import the VM's commits (auto fast-forward) and files |
| `slicer wt list` | List worktree VMs (`*` marks the current directory's VM) |

`path` defaults to `.` (the current directory).

Useful flags on `wt push`:

| Flag | Purpose |
|------|---------|
| `--launch` | Provision a fresh VM before pushing |
| `--depth N` | Shallow clone — much faster for large repos |
| `--force` / `-f` | Re-push into a VM that already has the worktree (wipes the VM-side copy first) |
| `--hostgroup NAME` | Host group for `--launch` |
| `--tag key=value` | Extra tags on the launched VM, or tags to match when `vm` is omitted |
| `--persistent` | Keep VM state across shutdown/restart; default `true` |
| `--rm` | Make the launched VM ephemeral, discarding state on stop/delete |

Useful flags on `wt pull`:

| Flag | Purpose |
|------|---------|
| `--force` / `-f` | If fast-forward is impossible, reset the host branch to the VM-side branch and overwrite tracked local changes |
| `--no-files` | Import refs only; do not overwrite working-tree files |
| `--no-merge` | Import refs but skip the automatic fast-forward |
| `--tag key=value` | Find the VM by matching tags when `vm` is omitted |
| `--verbose` / `-v` | Show additional review commands |

Useful flags on `wt list`:

| Flag | Purpose |
|------|---------|
| `--tag key=value` | Only list worktree VMs matching the tag; can be repeated |

## What `wt push` does for you

- Stages a **fresh, sanitised `.git`** — empty hooks, no foreign config — so the VM cannot reach or corrupt the host repo.
- Carries over **dirty and untracked files** (honouring `.slicerignore`).
- Points `origin` at the **https** upstream (rewriting `git@…` SSH remotes) so the VM can `git push` — including through Slicer Proxy in isolated-network VMs.
- Syncs your git identity (`user.name` / `user.email`) and safe preferences. **Credentials are never copied in.**
- Tags launched VMs with worktree metadata, repo name, branch, working directory, and client host/user, so `wt list`, `vm list`, and tag matching can find them later.

## What `wt pull` does for you

- Bundles the VM's commits and fetches them into namespaced refs `refs/slicer/<vm>/*` — your own branches and refs are never clobbered.
- Fast-forwards your current branch onto the VM's work, so agent commits land as real commits with a clean working tree.
- Brings back changed files.
- With `--force`, preserves the previous host `HEAD` under `refs/slicer` before resetting the host branch to the VM-side branch.

## ⚠️ One rule

**Don't edit the host worktree while a VM holds it.** `wt pull` overwrites host files with the VM's copy — anything you changed on the host since the push is lost. Push it, let the VM/agent work, pull it back. Treat the host worktree as "checked out to the VM".

## Agent sandbox worktree mode

The agent sandbox and workspace commands (`slicer codex`, `slicer amp`, `slicer claude`, `slicer copilot`, `slicer opencode`, `slicer pi`, and `slicer workspace` — see the `use-slicer` skill) accept `--worktree` / `--wt` to launch a VM, push the current git worktree, and attach in one command. Agent commands install the agent into that path; `slicer workspace` opens a clean shell VM instead:

```bash
slicer codex --worktree .     # launch Codex with the current worktree
# ...let the agent work and commit...
slicer wt pull codex-1 .      # bring the commits back, host branch fast-forwarded
git push
```

These VMs are persistent by default and can be relaunched/reused. Add `--rm` for a one-shot sandbox.

Avoid creating a provision-only agent sandbox first and then pushing into it unless you deliberately need that extra control. For normal agent work, `slicer <agent> --worktree .` is the intended path.

## Manual VM loop

```bash
cd ~/src/myrepo
git worktree add ../myrepo-feature -b feature
cd ../myrepo-feature
slicer wt push --launch .     # note the VM name it prints; persistent by default
# ...work in the VM and commit there...
slicer wt pull <vm> .
git push
```

## Availability

`slicer wt` is a recent addition. Run `slicer wt --help` to confirm it is present in your build, and update Slicer if the command is missing.
