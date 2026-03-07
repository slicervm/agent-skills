---
name: use-k3sup
description: Provision K3s clusters with alexellis/k3sup (single-node and HA via k3sup-pro) on Slicer VMs or remote hosts using SSH
tools: [Bash]
---

# Use k3sup — Provision K3s (Single-node + HA)

Use this when the user asks for:
- install Kubernetes
- create k3s cluster
- create k3s
- run k3sup
- setup single-node or HA k3s with `k3sup` / `k3sup-pro`

This skill handles both local-in-VM installs (via `--local`) and remote installs from your workstation using SSH.

`arkade` can provide the CLIs in Slicer images:

```bash
arkade get k3sup k3sup-pro
```

CLIs land in `~/.arkade/bin`. Add that path when needed:

```bash
export PATH="$PATH:$HOME/.arkade/bin"
```

---

## Single-node K3s inside a VM (or local Linux host)

For a VM where you can run commands directly, prefer `k3sup install --local`.

```bash
# inside a VM
arkade get k3sup
export PATH="$PATH:$HOME/.arkade/bin"
k3sup install --local
```

- `--local` installs K3s on the current host (no remote SSH needed).
- It writes a kubeconfig in the current directory with non-root ownership for the active user.
- Run `kubectl` with that kubeconfig in place, or copy it back as needed.

### Copy kubeconfig out of a Slicer VM

```bash
VM_NAME=sbox-1
slicer vm cp "$VM_NAME":/home/ubuntu/kubeconfig ./kubeconfig-local
```

---

## Slicer VM launched from this toolset (in-VM install)

Recommended flow:

1. Create/read VM name.
2. Ensure the VM has SSH access for remote-style tools if needed.
3. Install `k3sup` and run `k3sup install --local`.

```bash
WORKFLOW=k3s-$(date +%Y%m%d-%H%M%S)
VM_NAME=$(slicer vm add sbox --tag "workflow=$WORKFLOW" | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"

# Install k3sup tooling
slicer vm exec "$VM_NAME" --uid 1000 -- "arkade get k3sup"
slicer vm exec "$VM_NAME" --uid 1000 -- "export PATH=$PATH:$HOME/.arkade/bin && k3sup install --local"
```

If a VM is already running, reuse that existing VM only when explicitly reused for this session. Prefer fresh workflow-tagged VMs for new tasks.

---

## Remote install from your computer (Slicer VM or other host)

Use SSH-based install for machines you want to reach from the local machine.

```bash
VM_IP=192.168.64.10
export PATH="$PATH:$HOME/.arkade/bin"
arkade get k3sup
k3sup install --host "$VM_IP" --user ubuntu
```

For key-based auth, use the appropriate key flag for your environment (if needed):

```bash
k3sup install --host "$VM_IP" --user ubuntu --ssh-key "$HOME/.ssh/id_ed25519"
```

`--host` is the VM IP, `--user` is the SSH user (for Slicer VMs this is commonly `ubuntu`).

---

## SSH access for Slicer API-launched VMs

For VMs created through the Slicer API, `k3sup install --host` requires SSH access.
If SSH key injection was not provided at VM creation, add a public key before remote installation.

```bash
VM_NAME=sbox-1
PUBLIC_KEY="$(cat "$HOME/.ssh/id_ed25519.pub")"

slicer vm exec "$VM_NAME" --uid 1000 -- "mkdir -p ~/.ssh && chmod 700 ~/.ssh && printf '%s\n' \"$PUBLIC_KEY\" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

If you control VM creation, pass keys directly on launch (`--ssh-key` / `--github` on `slicer vm add`) to avoid this extra step.

---

## k3sup-pro HA clusters

For HA/multi-node installs use `k3sup-pro` with a `devices.json` containing all IPs and hostnames.

1. Create your devices JSON from hostnames/IPs.
2. Run plan, then apply.

```bash
cat > devices.json <<'EOF'
{
  "servers": [
    { "hostname": "k3s-server-1", "ip": "192.168.64.11" },
    { "hostname": "k3s-server-2", "ip": "192.168.64.12" }
  ]
}
EOF

k3sup-pro plan --user ubuntu
k3sup-pro apply --user ubuntu
```

Before running, run `k3sup-pro help` / `k3sup-pro plan --help` to confirm required JSON schema and flag names for your installed version.

---

## User preference reminders

- Use `slicer vm exec` for non-interactive operations and quick automation.
- Use `slicer vm shell` for interactive sessions only.
- Prefer `k3sup install --local` for in-VM bootstrap.
- Prefer remote `--host` workflows when installing from the user machine.
- Do not run cluster-exposure or forwarding commands inside `userdata` scripts; do that after VM readiness.
