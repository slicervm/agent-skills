---
name: use-slicer-proxy
description: Filter, audit, and inject secrets into HTTP(S) egress from Slicer microVMs with Slicer Proxy — default-deny allow rules, credential injection (Bearer, Basic, OAuth for Claude/Codex/Copilot/xAI), audit and passthrough modes — on Linux and macOS.
tools: [Bash]
---

# Slicer Proxy — filtered egress and secret injection for microVMs

Slicer Proxy is a daemon that runs alongside Slicer and becomes the only egress path for microVMs. Use it to:

- Audit and log every outbound HTTP(S) request from a VM
- Default-deny egress and allow only specific hosts / paths / methods / ports
- Inject credentials (Bearer, Basic, OAuth) so the VM never sees the real secret
- Expire rules automatically with a TTL
- Passthrough raw TCP (SSH, Postgres, cert-pinned clients) without TLS termination

This skill assumes a running Slicer daemon — see the `use-slicer` skill for connecting to one. Full docs: https://docs.slicervm.com/proxy/

## Concepts

Slicer Proxy separates three nouns:

- **client** — a name plus a token. The VM authenticates to the proxy with that token (carried in `HTTPS_PROXY`), which is how the proxy identifies it — no source-IP guessing.
- **secret** — a named upstream credential (`bearer`, `basic`, or an `oauth-*` type). The value lives on the proxy, never in the VM.
- **allow rule** — owned by a client: a `host` plus optional `paths` / `methods` / `ports` / `ttl`, and optionally a referenced `secret`.

**Default deny.** A client with no rules reaches nothing. An allow rule may be bare (just open a host) or reference a secret (inject a credential when it matches).

## Ports and bind address

- `:3128` — plaintext listener → `HTTP_PROXY=http://:<token>@<ip>:3128`
- `:3129` — TLS listener → `HTTPS_PROXY=https://proxy:<token>@<ip>:3129`
- Proxy IP: Linux defaults to `192.168.222.1` (set with `--bind`); macOS is `192.168.64.1` (the NAT gateway).

The `:3129` outer certificate is signed by the host group CA, so a guest that already trusts the Slicer CA validates it with no extra flags.

## Setup on Linux

Slicer Proxy only makes sense with **isolated networking** — the only mode where the proxy is the sole egress path. In bridge mode the VM has direct NAT'd Internet and bypasses the proxy entirely, so rules do nothing.

1. Generate an isolated config that drops all egress except the proxy ports:

```bash
slicer new sbox --count=0 \
  --net=isolated \
  --drop=0.0.0.0/0 \
  --allow=192.168.222.1:3128 \
  --allow=192.168.222.1:3129 \
  --find-ssh-keys=false \
  --ca \
  --socket ./slicer.sock \
  > slicer.yaml
```

2. Pre-generate the CA for the host group (writes `./.slicer/ca/sbox/`):

```bash
sudo slicer ca init --hostgroup sbox
```

3. Start the proxy (terminal 1). On Linux a concrete `--bind` IPv4 auto-creates a per-IP dummy adapter, which needs `sudo` (`CAP_NET_ADMIN`):

```bash
sudo slicer proxy up \
  --hostgroup sbox \
  --bind 192.168.222.1 \
  --deny-cidr 192.168.1.0/24
```

`--deny-cidr` blocks the proxy from dialing ranges *after* DNS resolution — always exclude your LAN range (consider `127.0.0.1/8` too). Deny-CIDRs win over any client allow rule.

4. Start Slicer (terminal 2). `slicer.yaml` is the default name, so no argument is needed:

```bash
sudo slicer up
```

## Setup on macOS

macOS support differs enough that this skill defers the exact steps to the docs — follow **https://docs.slicervm.com/proxy/mac/** and trust those instructions.

Key differences from Linux:

- **Two host groups.** `slicer` holds one long-lived VM — it can audit and inject secrets but **cannot block egress**. `sbox` holds ephemeral VMs and *can* be forced fully through the proxy.
- **Egress blocking is off by default.** Forcing traffic through the proxy is opt-in. Edit `~/slicer-mac/slicer-mac.yaml` on the `sbox` host group — set `ca: { generate: true }`, `network.dns_servers: ["127.0.0.1","127.0.0.1"]`, and `network.allow` / `network.drop` — then apply the host firewall rules with `sudo ~/slicer-mac/slicer-mac pf apply` (revert with `pf remove`). Without these edits `sbox` VMs keep full Internet access and the proxy only sees traffic that opts in. The docs page has the exact YAML diff.
- **Fixed proxy IP.** macOS uses the NAT gateway `192.168.64.1` — it is not configurable as it is on Linux.
- **Start flags.** Run `slicer proxy up` from `~/slicer-mac` with `--bind 0.0.0.0 --san 192.168.64.1 --seal-key-file ./.slicer/proxy/mk`; start Slicer with `slicer-mac up`.

Once set up, the client / secret / allow-rule workflow below is identical to Linux — use `192.168.64.1` as the proxy IP and drop `sudo` from the `slicer` commands.

## Core workflow

Register a client, grant it a host, launch a VM with the client token, and watch egress flow only through the proxy.

```bash
export SLICER_URL="./slicer.sock"          # or your daemon URL

# 1. Create a client; capture its token (printed bare on stdout)
PROXY_TOKEN=$(slicer proxy client create web-1)

# 2. Allow it to reach a host (everything else is denied)
sudo slicer proxy allow web-1 --host wikipedia.org

# 3. Launch a VM
slicer vm launch --tag role=web-1

# 4. Without the token: egress is blocked (DNS fails fast)
sudo slicer vm exec sbox-1 -- curl -sS --max-time 3 https://wikipedia.org

# 5. With the token in HTTPS_PROXY, egress flows through the proxy
sudo slicer vm exec \
  --env HTTPS_PROXY="https://proxy:$PROXY_TOKEN@192.168.222.1:3129" \
  sbox-1 -- curl -iS https://wikipedia.org
```

On macOS, drop `sudo` and use `192.168.64.1`.

Step 4 cannot even resolve DNS — the VM has no egress without the proxy. Step 5 returns `HTTP/2 301` (Wikipedia redirecting to `www.wikipedia.org`), proving the request reached the Internet through the proxy. Note `www.wikipedia.org` is a *different* host: following that redirect needs its own allow rule. Hostnames match exactly, or by wildcard (`*.wikipedia.org`).

Manage clients with `slicer proxy client list` and `slicer proxy client delete <name>` (deleting a client revokes its token and drops its rules).

## Allow rules

```bash
# Open a whole host (default ports 80 + 443)
slicer proxy allow web-1 --host archive.ubuntu.com

# Narrow by method + path (exact, or suffix-glob like '/system/*')
slicer proxy allow web-1 --host archive.ubuntu.com --method GET --path '/ubuntu/*'

# Narrow by upstream port
slicer proxy allow web-1 --host db.example.com --port 5432

# Allow every host (audit-style)
slicer proxy allow web-1 --host '*'

# Expire automatically after 1 hour
slicer proxy allow web-1 --host api.example.com --ttl 1h
```

Rules are **first-match-wins, in declaration order** — add the narrowest rule first. Multiple rules per host are allowed when methods or paths differ. `--host` accepts an exact name, a wildcard (`*.github.com`), or `*` for all.

Inspect and remove rules:

```bash
slicer proxy rules web-1                                  # list in declaration order (--json for raw)
slicer proxy revoke web-1 --host api.example.com          # bulk: every rule for that host
slicer proxy revoke web-1 --host api.example.com --method GET --path '/x'   # surgical: one rule
```

`revoke` is surgical when you repeat the flags used at create time, bulk-by-host otherwise.

## Secret injection

The proxy can attach a credential to matching requests so the VM never holds the real value.

```bash
# 1. Register the upstream credential on the proxy (value stays on the host)
slicer proxy secret create llm-key --host llama.example.com \
  --type bearer --value-file ./llm-token.txt

# 2. Reference it from an allow rule
slicer proxy allow web-1 --host llama.example.com --secret llm-key
```

Now a VM request to `https://llama.example.com/...` sent **without** an `Authorization` header has `Authorization: Bearer <secret>` injected by the proxy. The client's own `Authorization` header, if any, is stripped first.

Secret types (`--type`):

| Type | Value | Use |
|------|-------|-----|
| `bearer` (default) | token via `--value-file` | `Authorization: Bearer <value>` |
| `basic` | `user:pass` via `--value` | HTTP Basic auth |
| `oauth-claude` | `--value-file ~/.claude/.credentials.json` | Claude Code — proxy refreshes the token |
| `oauth-codex` | `--value-file ~/.codex/auth.json` | Codex / ChatGPT login |
| `oauth-github-copilot` | `--value-file ~/.local/share/opencode/auth.json` | GitHub Copilot |
| `oauth-xai` | `--value-file` from `slicer proxy oauth xai` | xAI Grok |

OAuth credentials are **adopted** — obtained on the host, handed to the proxy, then refreshed by the proxy — rather than injected mid-flow, so the VM can never capture a real token. Prefer `--value-file` over `--value` (which lands in shell history). Re-adopt after a fresh host-side login with `--force`.

For xAI, run the loopback login first:

```bash
slicer proxy oauth xai > ./xai-oauth.json
slicer proxy secret create xai --host api.x.ai --type oauth-xai --value-file ./xai-oauth.json
```

List and delete secrets with `slicer proxy secret list` / `slicer proxy secret delete <name>` (values are never returned).

## Audit mode — discover the paths a workload needs

Start the proxy with `--mode=audit` to log the method + path of denied HTTPS requests. It MITMs unknown TLS far enough to read the first inner request, logs it, then returns `403` without forwarding upstream:

```bash
sudo slicer proxy up --hostgroup sbox --bind 192.168.222.1 \
  --deny-cidr 192.168.1.0/24 --mode=audit
```

Log lines look like:

```
deny client=web-1 method=GET scheme=https host=api.example.com port=443 path=/v1/models mode=audit reason=no-rule
```

Use the output to write precise allow rules, then restart the proxy in the default `strict` mode for enforcement. Audit mode relies on the guest trusting the Slicer Proxy CA; pinned-cert clients fail closed (host-only logging).

## Passthrough — raw TCP (SSH, Postgres, pinned certs)

`--passthrough` splices TCP at CONNECT time without terminating TLS. Required for cert-pinned clients and non-HTTP protocols. It is mutually exclusive with `--secret` / `--method` / `--path` — the audit log carries only host, port, byte counts, and duration.

```bash
slicer proxy allow build-1 --host db.internal.example.com --port 5432 --passthrough
slicer proxy allow build-1 --host bastion.example.com --port 22 --passthrough
```

For SSH, set a `ProxyCommand` in `~/.ssh/config` on the host:

```
Host bastion
    ProxyCommand nc -x 192.168.222.1:3129 %h %p   # macOS: 192.168.64.1
```

## Transparent proxy helper

When setting `HTTP(S)_PROXY` per command is awkward, the in-VM helper redirects egress automatically with iptables. It needs the regular (non-`min`) image and the VM's DNS set to `127.0.0.1`.

```bash
# Inside the VM, as root — point it at the proxy with the client token
sudo slicer-agent proxy install 192.168.222.1 --token "$PROXY_TOKEN"
```

It also supports per-port TCP tunnels and an SSH `ProxyCommand` (the destination needs a `--passthrough` allow rule):

```bash
# In the VM:
sudo slicer-agent proxy tunnel add pg --listen 127.0.0.1:5432 db.internal:5432
ssh -o ProxyCommand='slicer-agent proxy connect %h:%p' user@bastion
```

See https://docs.slicervm.com/proxy/transparent/ for the helper, tunnel management, and Docker build caveats (containers need the CA at `/runner/ca.crt` added to their trust store).

## Notes

- **Linux: isolated mode only.** In bridge mode VMs have direct NAT egress and skip the proxy — rules then do nothing.
- The proxy is **default-deny**, and so is each client. Nothing leaves a VM until a client *and* an allow rule exist.
- `slicer proxy` requires a recent Slicer build — run `slicer proxy --help` to confirm it is present.
- Reset the CA: stop the daemons, `sudo rm -rf .slicer/ca/<hostgroup> proxy.crt proxy.key`, then re-run `slicer ca init`.
