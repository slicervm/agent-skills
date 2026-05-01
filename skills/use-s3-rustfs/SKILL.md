---
name: use-s3-rustfs
description: Install and run RustFS (S3-compatible object storage in Rust) in a Slicer VM, and talk to it with any S3 client (boto3, aws-cli, mc)
license: MIT
compatibility: Requires Bash, the Slicer CLI, a running Slicer daemon, and network access to install RustFS.
---

# Use S3 — RustFS in a Slicer VM

RustFS is a high-performance, S3-compatible object storage server written in Rust. Use it when you need a local S3 endpoint for:

- Development and CI against S3 APIs without touching AWS
- Integration tests for tools that speak S3 (boto3, aws-cli, `mc`, Terraform, etc.)
- Air-gapped or sandboxed object storage
- A throwaway S3 target for benchmarks

Upstream: https://rustfs.com — docs: https://docs.rustfs.com

This skill assumes you also have `use-slicer` — RustFS runs inside a Slicer microVM so it's isolated and disposable.

---

## TL;DR

```bash
# 1. Persistent sandbox VM, tagged so you can find it again
VM_NAME=$(slicer vm add sbox --persistent \
  --tag "workflow=rustfs" --tag "app=s3" \
  | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"

# 2. Install prereqs + RustFS (non-interactive)
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "sudo apt-get update -qq && sudo apt-get install -y -qq unzip curl"
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "curl -sSL -o /tmp/install_rustfs.sh https://rustfs.com/install_rustfs.sh && \
   printf '1\n9000\n\n\n\n\n\n\n' | sudo bash /tmp/install_rustfs.sh"

# 3. Forward the S3 API to the host (optional — only if you want host access)
slicer vm forward "$VM_NAME" -L 9000:127.0.0.1:9000 &
slicer vm forward "$VM_NAME" -L 9001:127.0.0.1:9001 &  # web console
```

Service is now listening on port **9000** (S3 API) and **9001** (web console) inside the VM, with default credentials `rustfsadmin` / `rustfsadmin` and data at `/data/rustfs0`.

---

## Why a VM?

RustFS wants to bind privileged directories (`/data/rustfs0`, `/var/logs/rustfs`) and install a systemd unit. Running it inside a disposable Slicer VM keeps your host clean, lets you snapshot/reset the storage instantly, and matches production-like deployment.

Always launch with `--persistent` + descriptive `--tag`s so the VM survives daemon restarts and can be rediscovered:

```bash
slicer vm list --json | jq -r '.[] | select(.tags.workflow=="rustfs") | .hostname'
```

On slicer-mac use the `sbox` host group explicitly. On Slicer for Linux, list groups first (`slicer vm group`) or omit the positional to use the default.

---

## Installation details

The official installer is interactive. Feed it default answers with a `printf` pipe:

```bash
printf '1\n9000\n\n\n\n\n\n\n' | sudo bash /tmp/install_rustfs.sh
```

The `1` picks "Install"; the remaining blank lines accept defaults for port, console port, data dir, access key, secret key, etc.

After install, config lives at `/etc/default/rustfs`:

```
RUSTFS_ACCESS_KEY=rustfsadmin
RUSTFS_SECRET_KEY=rustfsadmin
RUSTFS_VOLUMES="/data/rustfs0"
RUSTFS_ADDRESS=":9000"
RUSTFS_CONSOLE_ADDRESS=":9001"
RUSTFS_CONSOLE_ENABLE=true
```

Change keys before anything touches real data:

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  'access_key=$(openssl rand -hex 16) &&
   secret_key=$(openssl rand -hex 32) &&
   sudo sed -i \
     -e "s/^RUSTFS_ACCESS_KEY=.*/RUSTFS_ACCESS_KEY=${access_key}/" \
     -e "s/^RUSTFS_SECRET_KEY=.*/RUSTFS_SECRET_KEY=${secret_key}/" \
     /etc/default/rustfs &&
   sudo systemctl restart rustfs'
```

Service management:

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- "sudo systemctl status rustfs --no-pager"
slicer vm exec "$VM_NAME" --uid 1000 -- "sudo journalctl -u rustfs -n 50 --no-pager"
```

An unauthenticated GET on `/` returns **HTTP 403** when the server is healthy — that's the AWS-compatible "no anonymous access" response, not a failure.

---

## Talking to it with boto3

Endpoint `http://127.0.0.1:9000` (inside the VM, or via port-forward from the host):

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://127.0.0.1:9000",
    aws_access_key_id="rustfsadmin",
    aws_secret_access_key="rustfsadmin",
    region_name="us-east-1",
)

s3.create_bucket(Bucket="demo")
s3.put_object(Bucket="demo", Key="hello.txt", Body=b"hello\n")
print(s3.get_object(Bucket="demo", Key="hello.txt")["Body"].read())
```

Notes for S3 clients:

- Always pass `endpoint_url` — without it boto3 hits real AWS.
- `region_name` is required by the SigV4 signer, but RustFS ignores the value.
- Use **path-style** addressing for CLI tools — virtual-host style requires DNS for every bucket.
- No HTTPS by default. For TLS, terminate in front (nginx/caddy) or configure RustFS's TLS options.

### aws-cli

```bash
aws configure set default.s3.addressing_style path
aws --endpoint-url http://127.0.0.1:9000 \
    --no-verify-ssl s3 mb s3://demo
aws --endpoint-url http://127.0.0.1:9000 \
    s3 cp ./file.txt s3://demo/
```

Credentials via env: `AWS_ACCESS_KEY_ID=rustfsadmin AWS_SECRET_ACCESS_KEY=rustfsadmin`.

### MinIO client (`mc`)

```bash
mc alias set rustfs http://127.0.0.1:9000 rustfsadmin rustfsadmin
mc mb rustfs/demo
mc cp ./file.txt rustfs/demo/
```

---

## Web console

The console at port 9001 is a browser UI for browsing buckets, users, and policies. Forward it:

```bash
slicer vm forward "$VM_NAME" -L 9001:127.0.0.1:9001 &
open http://127.0.0.1:9001    # macOS
```

Log in with the same access/secret key.

---

## Testing from inside the VM

Prefer running tests in-VM — zero network hops and no port-forward juggling:

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "pip3 install --quiet --break-system-packages boto3"
slicer vm cp ./rustfs_test.py "$VM_NAME":/tmp/rustfs_test.py --uid 1000
slicer vm exec "$VM_NAME" --uid 1000 -- "python3 /tmp/rustfs_test.py"
```

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `curl http://127.0.0.1:9000/` returns **403** | Healthy — S3 requires auth; not a failure |
| Installer hangs on "Please choose an option" | Script is interactive. Pipe `printf '1\n9000\n\n\n\n\n\n\n'` in. |
| boto3: `InvalidAccessKeyId` | Keys in `/etc/default/rustfs` were changed; restart service after edit |
| boto3: `Could not connect to endpoint` | Port forward not running, or daemon down (`systemctl status rustfs`) |
| `CreateBucket` fails with signature error | Virtual-host addressing against `127.0.0.1`; switch to path-style |
| Data appears lost after VM delete | You deleted the persistent VM. Snapshot via `slicer vm suspend` or export disk first. |

---

## Reset / teardown

```bash
# Wipe just the data, keep the VM
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "sudo systemctl stop rustfs && sudo rm -rf /data/rustfs0/* && sudo systemctl start rustfs"

# Uninstall RustFS, keep the VM
slicer vm exec "$VM_NAME" --uid 1000 -- "printf '2\n' | sudo bash /tmp/install_rustfs.sh"

# Nuke the whole VM
slicer vm delete "$VM_NAME"
```
