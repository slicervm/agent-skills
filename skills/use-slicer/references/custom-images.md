# Base Images, Custom Images, and Userdata

## Published base images

Choose an image that matches both the daemon's hypervisor and the host
architecture. The published images currently documented by Slicer are:

| Operating system | Hypervisor | Architecture | Image | Default user |
|---|---|---|---|---|
| Ubuntu 22.04 | Firecracker | x86_64 | `ghcr.io/openfaasltd/slicer-systemd:5.10.240-x86_64-latest` | `ubuntu` |
| Ubuntu 22.04 | Firecracker | x86_64 | `ghcr.io/openfaasltd/slicer-systemd:6.1.90-x86_64-latest` | `ubuntu` |
| Ubuntu 22.04 | Firecracker | arm64 | `ghcr.io/openfaasltd/slicer-systemd-arm64:6.1.90-aarch64-latest` | `ubuntu` |
| Ubuntu 22.04 | QEMU | x86_64 | `ghcr.io/openfaasltd/slicer-systemd-ch:6.1.90-x86_64-latest` | `ubuntu` |
| Ubuntu 24.04 | Firecracker | x86_64 | `ghcr.io/openfaasltd/slicer-systemd-2404:5.10.240-x86_64-latest` | `ubuntu` |
| Rocky Linux 9 | Firecracker | x86_64 | `ghcr.io/openfaasltd/slicer-systemd-rocky9:5.10.240-x86_64-latest` | `slicer` |
| Arch Linux | Firecracker | x86_64 | `ghcr.io/openfaasltd/slicer-systemd-archlinux:6.1.90-x86_64-latest` | `slicer` |

Source of truth: <https://docs.slicervm.com/reference/images/>. Check it before
choosing an image when exact availability matters, because image tags and the
compatibility matrix can change.

The image belongs to the **daemon configuration**, not an individual VM. Select
it while generating the configuration:

```bash
# Rocky Linux 9 on Firecracker/x86_64
slicer new rocky9 \
  --image ghcr.io/openfaasltd/slicer-systemd-rocky9:5.10.240-x86_64-latest \
  > slicer.yaml

# Start the daemon, then launch VMs from that host group.
sudo -E slicer up ./slicer.yaml
slicer vm add rocky9
```

Or set `config.image` in an existing configuration before starting or restarting
the daemon:

```yaml
config:
  host_groups:
    - name: rocky9
      # other host-group settings
  image: ghcr.io/openfaasltd/slicer-systemd-rocky9:5.10.240-x86_64-latest
```

Do not pass `--image` to `slicer vm add`; that command creates a VM through an
already configured daemon. Since `config.image` is daemon-wide, use separate
daemon configurations when different base images must be available at the same
time. Use the image's default account when paths or SSH commands name the user
explicitly (`ubuntu` on Ubuntu; `slicer` on Rocky Linux and Arch), and use the
distribution's package manager (`apt`, `dnf`, or `pacman`) in userdata and
provisioning commands.

The older minimal Ubuntu image may still be accepted by some Slicer releases,
but it is not listed in the current published-image reference. Verify it against
the installed release before relying on it:

```text
ghcr.io/openfaasltd/slicer-systemd-min:6.1.90-x86_64-latest
```

## Building a custom image

1. Launch a VM with the default image
2. Customise it (install packages, configure services, etc.)
3. Export the disk to a new OCI image
4. Use the custom image in your config

```bash
# 1. Start a VM, customise it
VM_NAME=$(slicer vm add demo | awk '/Hostname:/ {print $2; exit}')
slicer vm ready "$VM_NAME"
slicer vm exec "$VM_NAME" --uid 1000 -- "sudo apt update && sudo apt install -y docker.io nginx golang"

# 2. Export the disk
slicer disk export "$VM_NAME" --output my-custom-image.img

# 3. Use it in a daemon config
slicer new mygroup --image ghcr.io/myorg/my-custom-image:latest > config.yaml
# Or set config.image in existing YAML
```

In YAML config, set the top-level `image:` field inside `config`:

```yaml
config:
  host_groups:
    - name: mygroup
      # other host-group settings
  image: ghcr.io/myorg/my-custom-image:latest
```

## Userdata (cloud-init style bootstrap)

Slicer supports userdata scripts — shell scripts that run once on first boot (similar to cloud-init). The script runs as root and is guarded by `/etc/slicer/userdata-ran` so it only executes once per disk.

Guideline: keep `userdata` strictly non-interactive and non-blocking.
- Scope: package install, user setup, and system configuration only.
- Avoid any long-running or interactive commands.
- Never use `kubectl port-forward`, `slicer vm forward`, background process launch, or shell interactivity in `userdata`.

```bash
# Inline
slicer vm add demo --userdata '#!/bin/bash
apt-get update && apt-get install -y docker.io
systemctl enable docker'

# From file
slicer vm add demo --userdata-file ./setup.sh

# In slicer new
slicer new demo --userdata-file ./setup.sh > config.yaml
```

Wait for userdata to finish before running commands:

```bash
slicer vm ready demo-1 --userdata --timeout 5m
```
