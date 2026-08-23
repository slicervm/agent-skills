---
name: use-dual-terminal-race
description: Record two coding agents racing the same task side by side — one agent per fresh Slicer microVM, each bridged into a host xterm (slicer vm shell) on a host Xvfb display, captured with ffmpeg. Use when asked to record a two-agent race, side-by-side model comparison, or dual-terminal demo video.
allowed-tools: Bash
---

# Use Dual-Terminal Race — two agents, two VMs, one video

Two opencode agents, each in its own fresh Slicer microVM, run the same task
side by side and are recorded as one video. The terminals are *real* xterms
on a *real* X server (Xvfb) **on the host**; each xterm bridges into its VM
with `slicer vm shell` and attaches to a guest tmux session.

This is the two-VM, host-display variant of `use-xvfb-terminal-recording`
(which runs Xvfb and xterm inside a single VM).

## Why this shape

- One VM per agent: each model gets a clean, identical machine; a failure or
  a stuck agent on one side cannot corrupt the other.
- Xvfb + xterm on the host: `slicer vm shell` gives a clean PTY per VM;
  xterm renders it with a real font; ffmpeg x11grabs the whole screen. No
  nested display plumbing, no per-VM X server.
- Guest tmux (`demo` session): the agent survives xterm/bridge reconnects,
  and you can drive and observe it with `tmux send-keys` /
  `tmux capture-pane` without touching the display.

## Prerequisites (host, once)

- `xvfb`, `xterm`, `fonts-dejavu-core`, `ffmpeg`, `imagemagick` (import),
  `x11-utils` (xwininfo) on the host.
- Slicer daemon running; `opencode` + `~/.local/share/opencode/auth.json` +
  `~/.config/opencode/opencode.json` on the host (they get copied into the
  VMs).
- An inlets tunnel for delivery (optional).

Start Xvfb if not running (must persist across execs):

```bash
DISPLAY=:99 Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
pgrep -a Xvfb && ls /tmp/.X11-unix/   # -> X99
```

## Step 1 — Provision the two VMs

```bash
slicer opencode --name ds --tag workflow=k3sup-race --tag model=deepseek
slicer opencode --name qw --tag workflow=k3sup-race --tag model=qwen
```

- No path argument: provision-only (VM + git identity + opencode creds +
  config + cached opencode binary). Nothing is copied from the host.
- **`--name` is essential**: the allocated hostname (e2e-N) is unpredictable
  after deletions; the friendly name is the stable handle.
- `slicer opencode` copies the host's opencode config and auth into each VM.

## Step 2 — Fix the config inside the VMs

The injected config may point a provider at a host-local address (e.g.
`sparks.baseURL = http://localhost:8900/v1`) that is wrong from inside a VM.
Correct it to the LAN-reachable address (e.g. `http://192.168.1.14:8900/v1`),
write the corrected config locally, then:

```bash
slicer vm cp ./opencode-vm.json ds:~/.config/opencode/opencode.json --uid 1000
slicer vm cp ./opencode-vm.json qw:~/.config/opencode/opencode.json --uid 1000
```

**Pin the model explicitly with `-m provider/model` at launch** — do not rely
on the config's default `model` for tests.

Smoke-test both endpoints from a VM before recording (a dead model mid-take
is an unrecoverable dead pane):

```bash
slicer vm exec ds -- 'curl -fsS -m 30 <endpoint>/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer <key>" -d "{\"model\":\"<model>\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: OK\"}],\"max_tokens\":10}"'
```

For OAuth providers (e.g. toilgate), extract the `access` token from
`~/.local/share/opencode/auth.json` and use it. Note the access token
lifetime (~1h); opencode refreshes automatically, but keep takes inside one
token's lifetime where possible.

## Step 3 — Optional: give the agents a map (skills)

Skills in `~/.config/opencode/skills/<name>/SKILL.md` (or
`~/.claude/skills/`) are auto-discovered by opencode in the VM. Copy the
relevant skill in so each model follows a verified flow but keeps its
liberties:

```bash
slicer vm cp ./SKILL.md ds:~/.config/opencode/skills/use-k3s/SKILL.md --uid 1000
slicer vm cp ./SKILL.md qw:~/.config/opencode/skills/use-k3s/SKILL.md --uid 1000
```

Verify discovery: `slicer vm exec ds -- 'cd ~ && opencode debug skill'`.

## Step 4 — Guest tmux + launch the agents

In each VM (as uid 1000):

```bash
tmux kill-session -t demo 2>/dev/null
tmux new-session -d -s demo -x 73 -y 41
tmux send-keys -t demo 'cd ~ && clear' Enter
sleep 1
tmux send-keys -t demo 'opencode --auto -m provider/model' Enter
```

- `-x 73 -y 41` matches the xterm geometry (73 cols x 41 rows per half).
- `--auto` auto-approves permission prompts; without it the agent stalls
  unattended.
- Wait for the splash, then confirm:
  `tmux capture-pane -t demo -p | tail -5` shows `~  ...  <version>`.

## Step 5 — xterms on the host display

**Kill stale xterms first** — when a VM is deleted the `slicer vm shell`
bridge dies but the xterm window lingers:

```bash
pkill -x xterm   # only if you own all xterms on this display
```

Then:

```bash
DISPLAY=:99 setsid xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
  -geometry 73x41+0+0 -title ds \
  -e slicer vm shell ds --bootstrap 'sleep 1; tmux attach -t demo' </dev/null >/dev/null 2>&1 &
DISPLAY=:99 setsid xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
  -geometry 73x41+955+0 -title qw \
  -e slicer vm shell qw --bootstrap 'sleep 1; tmux attach -t demo' </dev/null >/dev/null 2>&1 &
```

- **`-fa` (fontconfig face) with `-fs`** — `-fs` alone = tiny VGA font.
- `+0+0` and `+955+0` split the 1920px screen (880px windows each).
- Verify: `DISPLAY=:99 xwininfo -root -tree | grep -i xterm` (two 880x988
  windows), and inside each VM `tmux list-clients -t demo` (one client,
  73x41).

## Step 6 — Prompt, record, launch (the clean ordering)

1. Type the prompt into both input boxes (no Enter yet). Keep the prompt
   free of single quotes (it is single-quoted for the guest shell; opencode
   evals typed input and unbalanced quotes abort the run):

   ```bash
   slicer vm exec ds -- "tmux send-keys -t demo '$PROMPT'"
   slicer vm exec qw -- "tmux send-keys -t demo '$PROMPT'"
   ```

2. Confirm it sits in the composer:
   `tmux capture-pane -t demo -p | grep '<prompt-word>'`.
3. **Start ffmpeg before pressing Enter** — frame 1 is then the prompt in
   the input box, and model first-token latency is not dead screen time:

   ```bash
   DISPLAY=:99 setsid ffmpeg -y -loglevel error -f x11grab -video_size 1920x1080 \
     -i :99.0 -framerate 24 -t 900 -c:v libx264 -preset fast -pix_fmt yuv420p \
     /tmp/opencode/race-raw.mp4 </dev/null >/dev/null 2>&1 &
   ```

4. Flash Enter in both — **no stagger needed**; simultaneous reads fine:

   ```bash
   slicer vm exec ds -- 'tmux send-keys -t demo Enter'
   slicer vm exec qw -- 'tmux send-keys -t demo Enter'
   ```

## Step 7 — Monitor to completion

Poll the panes (never scrape the xterm):

```bash
slicer vm exec ds -- 'tmux capture-pane -t demo -p | grep -vE "^\s*$" | tail -12'
```

- `esc interrupt` in the status line = still working; cwd shown = turn done.
- Verify the outcome externally, not by the agent's self-report
  (`kubectl get nodes`, `curl` the endpoint, etc.).

When both are done: `pkill -x ffmpeg` (it also self-terminates at `-t`).

## Step 8 — Post: trim by pixel-diff MAD (not MD5)

Full-frame MD5 flips every second on a blinking cursor; use per-pixel mean
absolute difference over the **body region** (exclude the bottom ~40px
status strip). The `use-xvfb-terminal-recording` skill ships the tool
(`scripts/mad_trim.py`) — it walks the timeline, reports dead runs, suggests
the cut, applies it, and re-verifies:

```bash
# report only
python3 scripts/mad_trim.py race-raw.mp4

# apply the suggested cut (lead 3s before first real change,
# tail 3s after the last) and re-verify
python3 scripts/mad_trim.py race-raw.mp4 race-final.mp4

# tune buffers, or force an explicit cut
python3 scripts/mad_trim.py race-raw.mp4 race-final.mp4 --lead 2 --tail 6
python3 scripts/mad_trim.py race-raw.mp4 race-final.mp4 --start 17 --duration 107
```

Walk the whole timeline (front to back) and find:

- the **dead lead-in**: prompt-in-box, submit, model first-token wait
  (typically the first ~15–20s);
- any **dead middle** (there should be none);
- the **dead tail**: frozen final summaries.

Keep a **~3s buffer before the first real change** and a **~3s hold after
the last real change** (final summaries are a good ending).
Palette check: sample first/mid/last frames — expect the dark terminal
chrome (~`#0a0a0a`) with light text, not a black or single-colour frame.

## Step 9 — Deliver

- **Back up the previous video and index.html before swapping.**
- `python3 -m http.server 8300 --directory <dir>` + inlets tunnel; point
  `index.html`'s `<video src>` at the new file.
- Verify locally and publicly (ranged GET of the video).

## Step 10 — Clean up

```bash
slicer vm delete ds
slicer vm delete qw
```

## Gotchas

- **Stale xterms after VM deletion**: the `slicer vm shell` bridge dies but
  the xterm window lingers. `pkill -x xterm` before relaunching (only if you
  own the display).
- **`pkill tmux` kills every session on the guest** — kill by session name.
- **`slicer vm exec` with a backgrounded GUI hangs** the round-trip; xterm
  launches happen on the host here, so this only bites for in-VM daemons
  (use `slicer vm bg exec`).
- **Odd dimensions**: libx264 needs even width/height; 1920x1080 is fine,
  but if you crop to window size (e.g. 1902x1029) drop to 1902x1028.
- **Model first-token latency** (10–20s+ on reasoning models) is the main
  dead-lead-in source; the ffmpeg-before-Enter ordering plus the 3s buffer
  handles it.
- **Models do conservative inline `sleep`s**, which desyncs the two panes:
  one finishes and sits frozen on its "Done" summary while the other is still
  (apparently) waiting. In the prompt, ask for a **status check over a blind
  wait** ("once the pod is Running, do a single curl") and keep any wait
  short — avoid "…until it returns 200", which invites a retry loop. A
  per-pane MAD walk (split the frame at the pane divider, MAD each half)
  shows exactly which side went dead and when.
- **Permission gates**: `--auto` (or `permission: bash/edit allow` in the
  copied config) or the session stalls unattended.
- **Token lifetime**: OAuth access tokens (~1h) expire; opencode
  auto-refreshes, but keep takes inside one lifetime where possible.
- **Config drift**: the host config copied into VMs may reference
  host-local endpoints — fix per-VM before launch (step 2).
