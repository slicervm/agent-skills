# Slicer Daemon Setup (Linux)

Slicer is **not a SaaS** — it needs a running daemon. When none is running on your machine or LAN, generate a config and start your own. (To connect to a daemon that *already* exists, see "Connecting to a daemon" in the main `use-slicer` skill.)

## Generate a config

```bash
slicer new HOSTGROUP > config.yaml
```

Key flags for `slicer new`:

| Flag | Purpose |
|------|---------|
| `--count N` | Number of VMs to pre-launch (0 for API-only) |
| `--cpu N` | vCPUs per VM (default 2) |
| `--ram N` | RAM in GiB (default 4) |
| `--net isolated` | Isolated networking (no inter-VM traffic) |
| `--cidr 192.168.137.0/24` | Network range |
| `--api-bind 127.0.0.1` | TCP bind address |
| `--api-bind /tmp/slicer.sock` | Unix socket |
| `--api-auth=false` | Disable auth |
| `--image ghcr.io/...` | Custom rootfs image |
| `--storage image` | Persistent disk mode (default) |
| `--storage-size 25G` | Disk size |
| `--ssh-key "ssh-ed25519 ..."` | Inject SSH key |
| `--import-user USERNAME` | Import SSH keys from GitHub |
| `--userdata-file ./setup.sh` | Userdata script |
| `--graceful-shutdown=false` | Fast teardown |
| `--min` | Minimal image (faster boot, no Docker/K8s) |

## ⚠️ Avoid CIDR and host group conflicts

On Linux, multiple Slicer daemons can run simultaneously. **CIDRs and host group names must not overlap** across daemons — conflicts cause networking failures.

Before picking a CIDR range, check what's already in use:

```bash
# Check existing bridges and routes
ip addr show | grep -E "slicer|192\.168\.(137|138|139)"
ip route | grep 192.168

# Check for running slicer/firecracker processes
ps aux | grep -E "slicer|firecracker" | grep -v grep
```

Use distinct CIDRs per daemon (e.g. `192.168.137.0/24`, `192.168.138.0/24`, etc.) and unique host group names.

## Start a new daemon (local)

If no daemon is running, start one. **Check for conflicts first** — CIDRs and host group names must not overlap with any other running instance.

```bash
# Check for existing instances
ps aux | grep -E "slicer|firecracker" | grep -v grep
ip route | grep 192.168

# Generate config with a unique CIDR
slicer new sandbox --count=0 --graceful-shutdown=false \
  --api-bind=/tmp/slicer-sandbox.sock --api-auth=false \
  --cidr 192.168.140.0/24 > sandbox.yaml

# Start daemon
sudo -E slicer up ./sandbox.yaml > /tmp/slicer.log 2>&1 &
echo $! | sudo tee /run/slicer.pid

export SLICER_URL=/tmp/slicer-sandbox.sock
```

The plain foreground form is just:

```bash
sudo -E slicer up ./config.yaml
```

## Start a daemon on a remote machine over SSH

SSH into a remote/LAN machine, start Slicer there, then use the REST API remotely:

```bash
# On the remote machine (via SSH)
ssh user@192.168.1.50
slicer new sandbox --api-bind 0.0.0.0 --api-port 8080 > sandbox.yaml
sudo -E slicer up ./sandbox.yaml &

# Back on your local machine — use the remote API
export SLICER_URL=http://192.168.1.50:8080
export SLICER_TOKEN_FILE=./remote-token  # copy token from remote /var/lib/slicer/auth/token

# Remote Linux slicer endpoints typically already have pre-created VMs.
# Prefer reusing existing VMs from `slicer vm list` rather than creating new ones
# with `slicer vm add`, unless the user explicitly asks to create a VM.
slicer vm list --url "$SLICER_URL" --token-file "$SLICER_TOKEN_FILE"
```
