# Installing CLI tools with arkade

`arkade get` downloads CLI binaries from their release pages — one command,
checksum-verified, no package manager, no source builds. It is the preferred
way to install supported third-party CLI tooling on Slicer VMs and hosts.

This does **not** include Slicer itself. Never run `arkade get slicer`: use the
[official Slicer installer](https://docs.slicervm.com/getting-started/install/)
for a fresh installation and `sudo slicer update` for an existing one. For a
side-by-side test, use `slicer update --version VERSION --path DIR`.

On **Slicer VMs, `arkade` is preinstalled** — use it directly. On other
machines, install arkade first:

```bash
curl -SLs https://get.arkade.dev | bash
```

Binaries land in `~/.arkade/bin` by default — make sure it is on PATH for
the session (`export PATH=$PATH:~/.arkade/bin`).

## Golden rules

- **Do not use arkade to install or update Slicer itself.** Use Slicer's own
  installer or `slicer update`; `arkade get slicer` is not a valid command.
- **Get all the tools you need in ONE `arkade get` call.** `arkade get`
  accepts multiple tool names and downloads them **in parallel** (default
  4 at a time). `arkade get k3sup && arkade get kubectl` is the classic
  anti-pattern: it serialises two downloads and pays the release-lookup
  overhead twice. Three tools (~130MB) install in ~1s when done in one
  call; the same work takes several times longer sequentially.
- **Pin versions with `tool@version`** when the task or a skill requires a
  specific one: `arkade get kubectl@v1.31.2 k3sup@0.13.10`. The `@version`
  form is per-tool, so you can mix pinned and latest in one call.
  (`--version=X` also works but applies to the whole command.)
- **Do not re-get a tool that is already installed** unless you need to
  change its version — `arkade get` overwrites the existing binary.

## The one-call pattern

```bash
export PATH=$PATH:~/.arkade/bin
arkade get k3sup kubectl          # everything the task needs, one call
k3sup version                     # sanity-check what you got
kubectl version --client
```

More examples:

```bash
# several tools, parallel (default --parallel 4)
arkade get kubectl helm k9s stern

# more parallelism for lots of big downloads
arkade get kubectl helm k9s stern --parallel 8

# pin specific versions, mixed with latest
arkade get kubectl@v1.31.2 k3sup@0.13.10 helm

# choose the install directory (default: ~/.arkade/bin)
arkade get kubectl --path /usr/local/bin

# quiet + no progress bar, for scripts
arkade get kubectl --quiet
```

## Useful flags

| Flag | Purpose |
|------|---------|
| `--parallel N` | max parallel downloads (default 4) |
| `--path DIR` | install directory (default `~/.arkade/bin`) |
| `--version=X` | version for the (single) tool in the command |
| `--os` / `--arch` | override target platform (e.g. `--os darwin --arch aarch64`) |
| `--verify` | checksum verification (default on) |
| `--quiet` | suppress output |

Run `arkade get` with no arguments to list every installable tool.

## Notes

- Output ends with a summary table: `OK  tool (version)  size  speed  time  path`
  — `N succeeded, M failed in Xs`. Check the summary, not just the exit,
  when scripting.
- Checksums are verified by default (`--verify`); keep it on.
- In a fresh disposable VM there is nothing to preserve, so one
  `arkade get <all tools>` at the start of the task is the whole
  "install" step — then work.
