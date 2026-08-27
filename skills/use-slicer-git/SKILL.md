---
name: use-slicer-git
description: "Use Git with Slicer microVMs: launch coding sandboxes with a self-contained worktree, push or pull repositories with `slicer wt`, or fetch committed refs from an existing VM through `git daemon` and `slicer vm forward`."
allowed-tools: Bash
---

# Slicer Git — repositories and worktrees in microVMs

For coding agent sandboxes, prefer `slicer <agent> --worktree [path]`: it launches the VM, pushes a git worktree with a **working, self-contained `.git`**, installs the agent into that path, and attaches in one command.

Use lower-level `slicer wt push` when you are working with a plain VM, reusing a separately created VM, or need explicit control over the push/pull lifecycle. The host repository is never mounted and its hooks never run inside the VM.

This skill assumes a running Slicer daemon — see the `use-slicer` skill for connecting to one.

## Choose the Git flow

| Goal | Use |
|------|-----|
| Launch a coding sandbox from a host repository | `slicer <agent> --worktree PATH` |
| Move a host repository into an existing VM and later bring changes back | `slicer wt push` and `slicer wt pull` |
| Fetch committed refs from an arbitrary repository already in a VM | Short-lived `git daemon` through `slicer vm forward` |

Git transports only expose committed objects and refs. Commit dirty or
untracked VM work to a temporary recovery branch before using the live-server
flow. Use `slicer wt pull` when you deliberately need its separate file overlay.

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

## Fetch committed refs from a live VM

Use a short-lived `git daemon` when an existing VM repository should behave
like a read-only Git remote without using `slicer wt`. Git only serves committed
objects and refs: commit dirty and untracked work to a temporary recovery branch
inside the VM before fetching it.

Start the daemon as a background exec. Whitelist one exact repository, and bind
it to guest loopback:

```bash
VM_REF=e2e-3
REPO_PARENT=/home/ubuntu/go/src/github.com/openfaasltd
REPO_NAME=signet
REPO_GIT_DIR="$REPO_PARENT/$REPO_NAME/.git"

START=$(slicer vm bg exec "$VM_REF" --uid 1000 --cwd "$REPO_PARENT" --json \
  --cmd git \
  --arg daemon \
  --arg=--reuseaddr \
  --arg="--base-path=$REPO_PARENT" \
  --arg=--strict-paths \
  --arg=--export-all \
  --arg=--enable=upload-pack \
  --arg=--listen=127.0.0.1 \
  --arg=--port=9418 \
  --arg="$REPO_GIT_DIR")
GIT_EXEC_ID=$(printf '%s\n' "$START" | jq -r .exec_id)
test -n "$GIT_EXEC_ID" && test "$GIT_EXEC_ID" != null
```

`upload-pack` is Git daemon's default read-only service; spelling it out makes
the intended service explicit. With `--strict-paths`, a non-bare repository
must whitelist its exact `.git` directory. This prevents sibling repositories
beneath `REPO_PARENT` from being served. For a bare repository, set
`REPO_GIT_DIR` to the bare repository path instead.

Keep this blocking forward open in a second terminal or a tracked tmux session:

```bash
slicer vm forward "$VM_REF" -L 9418:127.0.0.1:9418
```

Clone or fetch from the host through that loopback listener:

```bash
git clone "git://127.0.0.1:9418/$REPO_NAME/.git" ./recovered-repo
git -C ./recovered-repo fetch origin
```

For a bare repository, omit `/.git` from the URL when it is not part of the
repository's directory name. If local port 9418 is already occupied, change
only the left-hand port in `-L`, then use that port in the host Git URL.

Stop the forward with `Ctrl-C`, then stop and reap the guest process:

```bash
slicer vm bg kill "$VM_REF" "$GIT_EXEC_ID" --grace 5s
slicer vm bg wait "$VM_REF" "$GIT_EXEC_ID" --timeout 10s || true
slicer vm bg remove "$VM_REF" "$GIT_EXEC_ID"
```

The `git://` protocol is unencrypted and unauthenticated. Keep the local forward
on `127.0.0.1`; never publish it with a `0.0.0.0` bind. For authentication and
encryption, forward guest SSH instead and use an SSH Git URL. Slicer does not
currently provide a `git-remote-slicer` helper.

## Availability

`slicer wt` is a recent addition. Run `slicer wt --help` to confirm it is present in your build, and update Slicer if the command is missing.
