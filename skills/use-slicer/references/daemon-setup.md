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
| `--net macvtap` | LAN-direct (Linux + Firecracker only) — see [networking.md](networking.md#macvtap-mode-lan-direct) |
| `--cidr 192.168.137.0/24` | Network range — for macvtap, this is your LAN gateway (e.g. `192.168.1.1/24`) |
| `--address 192.168.1.50` | Pin a specific IP (repeatable, macvtap mode) |
| `--api-bind 127.0.0.1` | TCP bind (loopback) — auth on by default, keep it |
| `--socket ./slicer.sock` | Unix socket bind — auth off by default, keep it |
| `--image ghcr.io/...` | Custom rootfs image |
| `--storage image` | Persistent disk mode (default) |
| `--storage-size 25G` | Disk size |
| `--ssh-key "ssh-ed25519 ..."` | Inject SSH key |
| `--import-user USERNAME` | Import SSH keys from GitHub |
| `--userdata-file ./setup.sh` | Userdata script |
| `--graceful-shutdown=false` | Fast teardown |
| `--min` | Minimal image (faster boot, no Docker/K8s) |

## Exposing the API: TCP vs Unix socket

How you bind the API also fixes the auth setting — `--api-auth` defaults to on for TCP and off for Unix sockets. **Leave `--api-auth` alone**: never disable it on a TCP bind (that publishes an unauthenticated control plane), and never add it on a socket (filesystem permissions already gate it).

- **Local use only → Unix socket.** Bind with `--socket ./slicer.sock`. Access is gated by filesystem permissions and the socket isn't reachable off-box, so auth stays off. Clients just point `SLICER_URL` at the socket path.
- **Local testing or a trusted LAN → TCP.** Use `--api-bind 127.0.0.1` for same-host clients, or `--api-bind 0.0.0.0` to reach the API from elsewhere on a trusted network. Auth stays on either way.
- **Public Internet → keep the API on loopback and front it.** Bind `--api-bind 127.0.0.1` and never expose `0.0.0.0` to the open Internet. Put a TLS terminator in front:
  - an [inlets](https://inlets.dev) tunnel — good behind NAT or without a public IP; inlets can terminate TLS for you; or
  - [Caddy](https://caddyserver.com) as a reverse proxy with automatic Let's Encrypt certificates, forwarding to the loopback API.

  See the [Slicer API reference](https://docs.slicervm.com/reference/api/) for both setups.

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

# Generate config with a unique CIDR.
# Local-only daemon — Unix socket, auth off by default (don't add it).
slicer new sandbox --count=0 --graceful-shutdown=false \
  --socket=/tmp/slicer-sandbox.sock \
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

`-E` matters: it preserves `HOME` so a root daemon still reads *your* license at `~/.slicer/LICENSE` rather than `/root/.slicer/LICENSE`. For an unattended service, set the license explicitly instead — see the next section.

## Run as a systemd service

For a host that should run Slicer on boot and restart on failure, install a systemd unit. Running directly as `User=root` is simplest — Slicer needs root for KVM and networking anyway, so this avoids a sudo wrapper and a sudoers change.

**Name the daemon's directory after its primary host group.** A `slicer.yaml` can define more than one host group, but `slicer new k3s` scaffolds the config around a primary host group `k3s` — name the directory to match, by convention. Keep the config, VM images, and per-daemon `.slicer/` state together in `/root/k3s/`:

```bash
sudo mkdir -p /root/k3s
slicer new k3s > /root/k3s/slicer.yaml
```

Then generate, install, enable, and start the systemd unit:

```bash
sudo slicer service generate --install \
  --name slicer-k3s \
  --working-directory /root/k3s \
  --timeout-stop-sec 180
```

```bash
sudo journalctl -u slicer-k3s -f --output=cat      # follow logs
```

**Why a dedicated directory.** In `storage: image` mode Slicer creates each VM's `.img` disk and the daemon's `.slicer/` state relative to `WorkingDirectory`. Pointing it at `/root/k3s` keeps everything for that daemon in one place — `slicer.yaml` alongside `k3s-1.img`, `k3s-2.img`, … (and the `.img` files for any other host groups the config defines) — so the daemon's whole footprint is a single directory you can size, back up, or delete as a unit. Choose a path with enough free space (not `/`). `storage: zvol` / `devmapper` keep disks in their pools instead, so the directory then only holds config and `.slicer/` state.

**License — point the unit at the real file, don't copy it.** `slicer service generate --install` writes an explicit `--license-file` into `ExecStart`. When run through `sudo`, it resolves the invoking user's `~/.slicer/LICENSE`; with `--user`, it resolves that user's license instead. Pass `--license-file` when you need a specific path.

**Stop timeout.** With `graceful_shutdown` on, Slicer waits up to ~120s for VMs to power off cleanly when the daemon is told to stop. `--timeout-stop-sec 180` gives it that room.

To add more host groups, edit them into the same `slicer.yaml` — that does not need a new directory or unit. A second daemon is only warranted when you want genuine isolation (separate API socket, non-overlapping CIDR); then repeat with its own `/root/<hostgroup>/slicer.yaml` and a matching `--name slicer-<hostgroup>`. To stop or disable: `sudo systemctl stop slicer-k3s` / `sudo systemctl disable slicer-k3s`.

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
