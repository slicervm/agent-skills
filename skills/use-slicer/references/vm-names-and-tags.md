# VM Names and Mutable Tags

Keep the generated hostname and the friendly name as separate concepts:

- **Hostname**: canonical API identity allocated from the host group, such as
  `sbox-4`.
- **Name**: optional CLI convenience stored as the well-known `name=<value>`
  tag, such as `name=papermaking`.
- **Tags**: metadata strings used for selection, ownership, workflows, and
  automation.

## Assign and use a friendly name

Prefer `--name` / `-n` over spelling the well-known tag manually:

```bash
slicer vm add sbox --name papermaking \
  --tag workflow=documentation --wait

slicer shell papermaking
slicer vm exec papermaking -- "uname -a"
slicer vm cp papermaking:~/guide.html .
slicer vm delete papermaking
```

Agent and workspace provisioners accept the same flag:

```bash
slicer opencode --name papermaking
slicer opencode papermaking
```

`slicer vm fork` also accepts `--name` for the newly allocated child.

Do not pass both `--name papermaking` and `--tag name=papermaking`; the CLI
rejects the duplicate forms before creating a VM.

Names must be unique lowercase DNS labels of at most 63 characters. They
cannot collide with another friendly name, an existing hostname, or Slicer's
generated hostname namespace. A name is preserved with a persistent VM's
suspended and stopped records, and cannot be renamed with `vm tag`.

## Understand CLI resolution

VM-targeting CLI commands accept either the canonical hostname or the friendly
name. The CLI first sends the supplied identifier unchanged. Only after a 404
does it query for the exact `name=<identifier>` tag and retry with the returned
canonical hostname.

In Slicer CLI 0.1.210, `slicer vm bg kill` is the known exception: its explicit
VM argument is sent directly without the fallback. Pass the canonical hostname
returned at launch for `bg kill`; the other `bg` management commands accept the
friendly name. Treat this as a temporary CLI consistency defect, not a reason
to add name resolution to the API or SDK.

Keep this direct-first behaviour when extending the CLI. Do not add server-side
alias middleware, an `/alias` or `/name` route, a `name` request field, or an
SDK-level name primitive.

## Inspect and mutate tags

```bash
slicer vm tag list papermaking
slicer vm tag add papermaking --tag owner=alex --tag purpose=docs
slicer vm tag remove papermaking --tag owner=alex
slicer vm tag replace papermaking --tag purpose=release
```

Tag updates are atomic. `replace` replaces all mutable tags but preserves the
immutable `name=` tag; calling it without `--tag` clears only mutable tags.
Attempts to change or remove an assigned `name=` through `vm tag` fail.

The built-in slicer-mac VM, `slicer-1`, is the one assignment exception: if it
does not already have a name, assign one once with
`slicer vm tag add slicer-1 --tag name=linux-twin`. It is immutable
afterwards.

`slicer vm list` renders the friendly value in the `NAME` column and omits the
well-known name tag from the human `TAGS` column. Use `slicer vm tag list` or
`slicer vm list --json` to inspect the underlying tag array.

## Use the API or SDK

The API has tags, not a separate name resource. Put the well-known tag in the
ordinary launch tags:

```json
{"count":1,"tags":["name=papermaking","workflow=documentation"]}
```

Resolve a friendly name by filtering the collection, then use the returned
hostname for VM endpoints:

```text
GET /nodes?tag=name%3Dpapermaking
GET /vm/sbox-4
```

Require exactly one exact tag match. In Go, use `ListVMs` with
`sdk.ListOptions{Tag: "name=papermaking"}`, then pass the returned `Hostname`
to VM methods. Use `UpdateVMTags`, `AddVMTags`, `RemoveVMTags`, or
`ReplaceVMTags` for mutable metadata. When replacing tags, omit the immutable
`name=` tag from the replacement; the server preserves it. Supplying even the
same `name=` value in a replacement is rejected as an attempted rename. In
TypeScript, use `VM.getTags()`,
`updateTags()`, `addTags()`, `removeTags()`, and `replaceTags()` on a handle
attached by canonical hostname.

Linux Slicer and slicer-mac both persist tag updates. Neither backend resolves
friendly names in API paths; that convenience belongs to the Slicer CLI.
