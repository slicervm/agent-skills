---
name: use-slicer-worktrees
description: Move a git worktree or repository into a Slicer microVM with a working, self-contained .git — push code in with `slicer wt push`, let a VM or coding agent work, then pull commits back. The recommended way to put a git project into an agent sandbox.
tools: [Bash]
---

# Slicer Worktrees — git worktrees and repos inside a microVM

`slicer wt` moves a git worktree (or a whole repository) into a Slicer microVM with a **working, self-contained `.git`**, lets the VM — or a coding agent running in it — do the work, then pulls the commits back. The host repository is never mounted and its hooks never run inside the VM.

This skill assumes a running Slicer daemon — see the `use-slicer` skill for connecting to one.

## Why `slicer wt` (and not a plain copy)

A git **worktree**'s `.git` is a *file*, not a directory:

```
gitdir: /home/you/src/project/.git/worktrees/feature-x
```

That is an **absolute host path**. Tar-copying the worktree directory into a VM leaves the pointer dangling — every git command in the VM fails with `fatal: not a git repository`. And even for a normal repo, copying `.git` wholesale drags host hooks and config along.

`slicer wt push` stages a fresh, sanitised `.git` instead, so git works correctly in the VM and the host repo stays untouchable.

## Quick start

```bash
slicer wt push --launch .     # launch a VM and push the current worktree in
slicer vm shell <vm>          # work in it — or point a coding agent at it
slicer wt pull <vm> .         # commits + files back, your branch fast-forwarded
git push                      # from the host, under your own identity
```

`<vm>` is the VM name printed by `wt push --launch`.

## Commands

| Command | Purpose |
|---------|---------|
| `slicer wt push [vm] [path]` | Push the worktree at `path` into an existing VM |
| `slicer wt push --launch [path]` | Launch a fresh VM, then push |
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
| `--tag key=value` | Extra tags on the launched VM |

## What `wt push` does for you

- Stages a **fresh, sanitised `.git`** — empty hooks, no foreign config — so the VM cannot reach or corrupt the host repo.
- Carries over **dirty and untracked files** (honouring `.slicerignore`).
- Points `origin` at the **https** upstream (rewriting `git@…` SSH remotes) so the VM can `git push` — including through Slicer Proxy in isolated-network VMs.
- Syncs your git identity (`user.name` / `user.email`) and safe preferences. **Credentials are never copied in.**

## What `wt pull` does for you

- Bundles the VM's commits and fetches them into namespaced refs `refs/slicer/<vm>/*` — your own branches and refs are never clobbered.
- Fast-forwards your current branch onto the VM's work, so agent commits land as real commits with a clean working tree.
- Brings back changed files.

## ⚠️ One rule

**Don't edit the host worktree while a VM holds it.** `wt pull` overwrites host files with the VM's copy — anything you changed on the host since the push is lost. Push it, let the VM/agent work, pull it back. Treat the host worktree as "checked out to the VM".

## Pairing with agent sandboxes

The agent sandbox commands (`slicer codex`, `slicer amp`, `slicer claude`, `slicer copilot`, `slicer opencode` — see the `use-slicer` skill) run **provision-only** when given no positional argument: they create a VM with the agent installed but copy nothing in. That is the intended entry point for `slicer wt`:

```bash
slicer codex                  # provision a clean codex VM (no workspace copied)
slicer wt push codex-1 .      # push your worktree in, with a working .git
slicer codex codex-1          # attach; let the agent work and commit
slicer wt pull codex-1 .      # bring the commits back, host branch fast-forwarded
git push
```

## Typical loop

```bash
cd ~/src/myrepo
git worktree add ../myrepo-feature -b feature
cd ../myrepo-feature
slicer wt push --launch .     # note the VM name it prints
# ...work, or run an agent, in the VM and commit there...
slicer wt pull <vm> .
git push
```

## Availability

`slicer wt` is a recent addition. Run `slicer wt --help` to confirm it is present in your build, and update Slicer if the command is missing.
