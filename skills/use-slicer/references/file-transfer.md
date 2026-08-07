# File Transfer

Use binary mode for one file and recursive tar mode for directories.

## Single files

```bash
slicer vm cp ./local-file.txt VM_NAME:/tmp/file.txt --uid 1000
slicer vm cp VM_NAME:/etc/os-release ./os-release.txt

slicer vm cp ./script.sh VM_NAME:/tmp/script.sh \
  --mode=binary --permissions 0755 --uid 1000
```

When the local destination is an existing directory, the downloaded file uses
the remote source basename:

```bash
slicer vm cp VM_NAME:~/papermaking-guide.html .
```

## Directories

Always pass `-r` / `--recursive` for a directory in either direction:

```bash
slicer cp -r ./my-project/ VM_NAME:/home/ubuntu/project/ --uid 1000
slicer cp -r VM_NAME:/home/ubuntu/project/results/ ./results/
```

Recursive mode uses tar. For VM-to-host copies, the local destination is a
directory and is created when absent. The source directory name is retained
when copying the directory itself; inspect the result before assuming files
were flattened into the destination.

## Exclusions

```bash
slicer cp -r ./src/ VM_NAME:/home/ubuntu/src/ --uid 1000 \
  --exclude '**/.git/**' --exclude '**/node_modules/**'
```

Host-to-VM recursive copies also read `.slicerignore` from the local source
directory. Use gitignore syntax. Exclude dependency caches, build outputs,
images, and datasets that the VM does not need, such as `node_modules/`,
`vendor/`, `target/`, `dist/`, `build/`, `.next/`, and `*.img`.

## Compatibility with older guests

The Slicer CLI may be newer than the `slicer-agent` in a published guest
image. Current clients try cp-v1 first and retry the legacy wire mode only when
an older guest rejects that exact mode. Binary and tar upload bodies are
replayable, so retrying them is safe.

If a copy fails with `invalid mode: cp-v1-binary`, `cp-v1-tar`, or
`cp-v1-recursive`, update the Slicer CLI to a build containing Go SDK v0.0.67
or later. Do not replace the guest agent or alter the daemon as the first fix.
Other 400 responses must still fail rather than trigger a legacy retry.
