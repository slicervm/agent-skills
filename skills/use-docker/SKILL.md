---
name: use-docker
description: Install and use a current Docker Engine release on Ubuntu, Debian, and Slicer VMs with Docker's official installer, non-root group access, systemd, Compose, image builds, and container runs. Use when asked to install Docker, prepare a Docker host or VM, build or run containers, use Docker Compose, or fix Docker daemon and socket access.
allowed-tools: Bash
---

# Use Docker Engine

## Installation policy

Prefer Docker's official installer so that Docker Engine comes from Docker's
repository and does not lag behind upstream releases.

- Never substitute `apt install docker.io`, `apt install docker-compose`, or
  similar distribution packages when the official installer supports the
  machine. Ubuntu and Debian packages can be significantly behind.
- Use APT-packaged Docker only as a last resort when the official installer is
  genuinely incompatible or unavailable, and state why the fallback is
  necessary.
- Do not reinstall Docker when a suitable working installation already exists.

## Install on Ubuntu, Debian, or a Slicer VM

Run the official installer, add the standard `ubuntu` user to the Docker
group, and ensure the daemon is enabled and running:

```bash
curl -LSs https://get.docker.com | sudo bash
sudo usermod -aG docker ubuntu
sudo systemctl enable --now docker
```

Membership of the `docker` group grants root-equivalent access. Add only the
intended trusted user.

For a non-Slicer machine whose login user is not `ubuntu`, replace `ubuntu`
with that non-root login name. Do not add `root` to the group.

## Use the new group membership

An existing shell does not automatically gain a newly added supplementary
group. Reconnect to the machine before running `docker` directly, or use `sg`
for commands that must run immediately:

```bash
sg docker -c 'docker version'
sg docker -c 'docker run --rm hello-world'
```

In longer-lived automation, keep the command inside `sg docker -c '...'` until
the session has been recreated. Do not weaken the socket permissions with
`chmod 666 /var/run/docker.sock`.

## Build, run, and compose

After reconnecting, use Docker normally:

```bash
docker build -t myapp:latest .
docker run --rm -p 8080:8080 myapp:latest
docker compose up -d
```

Before assuming an old standalone `docker-compose` binary is required, try
the current Compose plugin:

```bash
docker compose version
```

## Diagnose failures

Check the service and socket without changing daemon configuration:

```bash
sudo systemctl status docker --no-pager
sudo journalctl -u docker --no-pager -n 100
ls -l /var/run/docker.sock
```

- `permission denied` on the socket usually means the shell predates the group
  change; reconnect or use `sg docker -c '...'`.
- `Cannot connect to the Docker daemon` usually means the service is stopped;
  run `sudo systemctl enable --now docker` and inspect the journal if it fails.
- Do not make speculative storage-driver or `daemon.json` changes for ordinary
  installation or permissions problems.
