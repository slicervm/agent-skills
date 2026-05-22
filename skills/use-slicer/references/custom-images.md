# Custom Images and Userdata

## Default images

- `ghcr.io/openfaasltd/slicer-systemd:5.10.240-x86_64-latest` (full, with Docker/K8s kernel support)
- `ghcr.io/openfaasltd/slicer-systemd-min:6.1.90-x86_64-latest` (minimal, faster boot)
- `ghcr.io/openfaasltd/slicer-systemd-arm64:6.1.90-aarch64-latest` (ARM64)

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

# 3. Use it in config
slicer new mygroup --image ghcr.io/myorg/my-custom-image:latest > config.yaml
# Or set the image: field in existing YAML
```

In YAML config, set the `image:` field under a host group:

```yaml
config:
  host_groups:
    - name: mygroup
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
