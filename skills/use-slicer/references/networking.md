# Slicer Networking Reference

## Network Modes

Slicer supports two networking modes, set at config generation time via `slicer new --net`:

### Bridge Mode (default)

```bash
slicer new demo --cidr 192.168.137.0/24
```

- VMs get IPs on a shared bridge (e.g. `192.168.137.2`, `.3`, etc.)
- VMs can talk to each other, the host, and the internet
- Host acts as gateway and NAT for outbound traffic
- DNS is configured automatically via systemd inside the guest
- **Services are reachable by IP**: if nginx runs on `0.0.0.0:80` inside a VM, it's accessible at that VM's bridge IP (e.g. `192.168.137.2:80`) from the host and other VMs
- Best for: development, multi-VM clusters (k3s), general use

### Isolated Mode

```bash
slicer new demo --net isolated --allow "0.0.0.0/0" --drop "10.0.0.0/8"
```

- Each VM gets a point-to-point link — no inter-VM traffic
- **Egress only by default** — VMs can reach the internet but nothing can reach into them unless you use port forwarding
- Firewall rules control outbound access
- `--allow` and `--drop` accept CIDR blocks to whitelist/blacklist destinations
- Default isolated range: `169.254.100.0/22`
- Best for: untrusted code execution, CI runners, sandboxes

### macOS (slicer-mac)

- VMs **cannot** talk to each other
- VMs **can** talk to the macOS host
- The `slicer` host group is a persistent Linux twin (survives reboots)
- The `sbox` host group is for ephemeral API-launched sandboxes
- Socket auto-detected at `~/slicer-mac/slicer.sock` — no `--url` needed

### CIDR and host group conflicts

On Linux, multiple Slicer daemons can coexist. **CIDRs and host group names must be unique across daemons** — overlapping ranges or names cause bridge/routing conflicts.

Check before creating a new daemon:

```bash
ip addr show | grep -E "slicer|192\.168\.(137|138|139)"
ip route | grep 192.168
ps aux | grep -E "slicer|firecracker" | grep -v grep
```

Use distinct ranges per daemon (e.g. `192.168.137.0/24`, `192.168.138.0/24`).

Key flags for isolated mode:

| Flag | Purpose |
|------|---------|
| `--net isolated` | Enable isolated networking |
| `--allow CIDR` | Allow outbound to this range (repeatable) |
| `--drop CIDR` | Block outbound to this range (repeatable) |
| `--isolated-range CIDR` | Override the link-local range (default `169.254.100.0/22`) |

## Accessing VMs from Other Machines

If you run Slicer on a remote server and need to reach VM IPs from your laptop:

```bash
# Show route commands for your OS
slicer vm route ./config.yaml
slicer vm route ./config.yaml --os darwin   # macOS only
slicer vm route ./config.yaml --os linux    # Linux only
```

This prints the `ip route add` / `route add` commands to route the VM subnet through the Slicer host.

## Port Forwarding (vsock-based)

Port forwarding uses the slicer-agent inside the VM (vsock), not the network bridge. This means:

- Forwarding works in both bridge and isolated modes
- No firewall rules needed — traffic goes through the slicer API
- Supports TCP ports, Unix sockets, and socket-to-TCP bridging
- Multiple `-L` specs can be combined in one command

```bash
# Forward syntax: -L [local_bind:]local_port:remote_host:remote_port
# Or for sockets: -L local_path:remote_socket_path

slicer vm forward VM -L 8080:127.0.0.1:8080        # TCP
slicer vm forward VM -L /tmp/d.sock:/var/run/docker.sock  # Unix socket
slicer vm forward VM -L 2375:/var/run/docker.sock   # Socket → TCP
```

## SSH Access

SSH is pre-installed on every image. Keys are injected via:

1. Auto-scanning `~/.ssh/*.pub` on the host (default, disable with `--find-ssh-keys=false`)
2. `--ssh-key "ssh-ed25519 AAAA..."` flag (repeatable)
3. `--github USERNAME` to import from GitHub

Forward SSH for SCP/rsync:

```bash
slicer vm forward VM -L 2222:127.0.0.1:22 &
ssh -p 2222 ubuntu@127.0.0.1
scp -P 2222 file.txt ubuntu@127.0.0.1:/tmp/
rsync -e "ssh -p 2222" ./src/ ubuntu@127.0.0.1:/home/ubuntu/src/
```

## DNS

DNS inside guests is configured automatically by the `mount-config` systemd service during boot. It uses the host's resolvers. No manual DNS setup is needed.

## API Bind Options

The Slicer API server can listen on:

| Bind | Example | Auth |
|------|---------|------|
| TCP (loopback) | `--api-bind 127.0.0.1 --api-port 8080` | Enabled by default |
| TCP (all interfaces) | `--api-bind 0.0.0.0` | Enabled by default |
| Unix socket | `--api-bind /tmp/slicer.sock` | Disabled by default |

For TCP, auth uses Bearer tokens from `/var/lib/slicer/auth/token` (or `config.api.auth.token`).

Unix sockets rely on filesystem permissions — auth is off by default but can be enabled with `--api-auth`.
