---
name: use-xvfb-terminal-recording
description: Record a terminal or TUI (coding agent) demo as a real, watchable video using Xvfb + xterm + ffmpeg x11grab inside a Slicer VM. Use when asked to record a terminal demo, capture an agent run as video, produce a screen recording of a CLI session, or trim/deliver such a recording.
allowed-tools: Bash
---

# Use Xvfb Terminal Recording — real video of a real terminal

Render the terminal with a *real* terminal emulator (xterm) on a *real* X
server (Xvfb) and capture the screen with ffmpeg, exactly as a human would
see it. Do NOT hand-render frames from an asciinema cast or `tmux
capture-pane` + Pillow: re-implementing a terminal emulator and font
rasteriser produces broken output (tofu holes, glyph shear, dropped
timing).

Verified on Slicer VMs (Ubuntu 22.04) 2026-08-14/15. Companion skill for the
two-VM side-by-side variant on a host display: `use-dual-terminal-race`.

## Prerequisites (install once in the VM, as root)

```bash
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  xvfb xterm fonts-dejavu-core ffmpeg x11-utils imagemagick
```

`x11-utils` gives `xwininfo` (window geometry), `imagemagick` gives `import`
(stills).

## Step 1 — Start Xvfb

```bash
# as uid 1000; must persist across execs — bg exec or setsid
DISPLAY=:99 Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
```

Verify: `pgrep -a Xvfb` and `ls /tmp/.X11-unix/` → `X99`.

## Step 2 — Build the tmux layout

One tmux **session per agent/pane** (not two panes of one session) so tools
that address agents by session work:

```bash
tmux new-session -d -s left -x 73 -y 41
tmux new-session -d -s right -x 72 -y 41
tmux send-keys -t left 'cd ~ && clear' Enter
tmux send-keys -t right 'cd ~ && clear' Enter
# launch the agent in each — WITH auto-approval:
tmux send-keys -t left 'opencode --auto -m provider/model' Enter
tmux send-keys -t right 'opencode --auto -m provider/model' Enter
```

- opencode: `--auto` auto-approves permission prompts. **Without it the
  agent locks on "⚠ Permission required … Allow once / Allow always /
  Reject" and the demo stalls.** (Equivalent to Claude Code's
  `--dangerously-skip-permissions`.) Pin the model explicitly with `-m` for
  tests — do not rely on the config default.
- Wait for the splash, then confirm with
  `tmux capture-pane -t left -p | tail -5` (shows `~  ...  <version>`).

## Step 3 — xterms on the display

```bash
DISPLAY=:99 setsid xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
  -geometry 73x41+0+0 -e tmux attach -t left </dev/null >/dev/null 2>&1 &
DISPLAY=:99 setsid xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
  -geometry 73x41+955+0 -e tmux attach -t right </dev/null >/dev/null 2>&1 &
```

- **`-fa 'DejaVu Sans Mono'` together with `-fs`.** `-fs` alone leaves xterm
  on its tiny fallback VGA font (~6px/char) — the capture is unreadable. This
  is the #1 cause of "black/blank video".
- `-geometry COLSxROWS+X+Y` must match the tmux session size (`-x/-y`) so
  nothing wraps or rescales.
- `setsid … </dev/null &` so the launch round-trip returns.
- Verify geometry: `DISPLAY=:99 xwininfo -root -tree | grep -i xterm`.

Optional still before committing: `DISPLAY=:99 import -window root
/tmp/still.png`. Check the palette is the UI's real colours (dark chrome,
light text, accents) — a black or single-colour frame means a font/geometry
problem, not a recording problem.

## Step 4 — The clean ordering (this is what separates a watchable take)

1. **Type the prompt into the input box — do NOT press Enter yet.**
   `tmux send-keys -t left '<prompt>'` (no Enter).
2. Confirm it sits in the composer:
   `tmux capture-pane -t left -p | grep '<prompt-word>'`.
3. **Start ffmpeg.**
4. **Now press Enter** (`tmux send-keys -t left Enter`).

Frame 1 is then the prompt already in the input box, and the model's
first-token latency (10–20s+ on reasoning models) is *not* dead screen time.
Do NOT start ffmpeg, sleep a fixed time, then prompt: that puts first-token
latency at frame 0 and reads as a stall. Staggering the two sides' Enters is
optional — simultaneous is fine.

```bash
DISPLAY=:99 setsid ffmpeg -y -loglevel error -f x11grab -video_size 1920x1080 \
  -i :99.0 -framerate 24 -t 900 -c:v libx264 -preset fast -pix_fmt yuv420p \
  /tmp/take-raw.mp4 </dev/null >/dev/null 2>&1 &
```

**Even dimensions required by libx264**: if you crop to window size (e.g.
1902x1029, odd height), capture 1902x1028. Full 1920x1080 is fine.

## Step 5 — Monitor to completion (drive via tmux, not the display)

```bash
tmux capture-pane -t left -p | grep -vE '^\s*$' | tail -12
```

- Status line shows `esc interrupt` = still working; cwd shown = turn done.
- Verify the outcome externally (run the commands, curl the endpoint) —
  never trust a self-reported "done".
- When both are done: `pkill -x ffmpeg` (it also self-terminates at `-t`).

## Step 6 — Trim by pixel-diff MAD (NOT full-frame MD5)

Full-frame MD5 flips every second on a blinking cursor or status-bar clock,
yet the story is frozen (learned the hard way: MD5 showed "118/120 unique"
on a take that was actually static from frame 15). Use per-pixel **mean
absolute difference** against the previous frame, over the **body region
only** (exclude the bottom ~40px status strip, which always repaints):
`mad > 0.5` = real story change, `mad < 0.01` = frozen.

**Use the bundled script** — it does the walk, reports dead runs, suggests
the cut, applies it, and re-verifies:

```bash
# report only (profile + dead runs + suggested cut)
python3 scripts/mad_trim.py take-raw.mp4

# apply the suggested cut (lead 3s before first real change,
# tail 3s after the last) and re-verify
python3 scripts/mad_trim.py take-raw.mp4 take-final.mp4

# tune the buffers, or force an explicit cut
python3 scripts/mad_trim.py take-raw.mp4 take-final.mp4 --lead 2 --tail 6
python3 scripts/mad_trim.py take-raw.mp4 take-final.mp4 --start 17 --duration 107
```

Walk the whole timeline front to back and find:

- the **dead lead-in** (prompt-in-box → submit → first-token wait);
- any **dead middle** (there should be none);
- the **dead tail** (frozen final output).

Keep a **~3s buffer before the first real change** (viewer sees the prompt
state briefly) and a **~3s hold after the last real change** (final summary
is a good ending). Pairwise 2-frame changes near the end are cursor/LSP
blink, not story — the script's dead-run report shows them; verify before
extending the tail.

## Step 7 — Deliver

Serve a page, not a raw file, through one tunnel so the URL stays stable as
revisions are swapped:

```bash
python3 -m http.server 8300 --bind 0.0.0.0 --directory /tmp/opencode &
inlets-pro cloud create <name>
inlets-pro uplink client --url=wss://.../<name> --token=... \
  --upstream=<domain>=http://127.0.0.1:8300
```

- **Back up the previous video and index.html before swapping.**
- Point `index.html`'s `<video src>` at the new file.
- Verify locally (`curl 127.0.0.1:8300/`) and publicly (ranged GET of the
  video).

## Gotchas

- **`pkill tmux` kills every session on the server** — kill by session name
  (`tmux kill-session -t X`).
- `slicer vm exec` with a `… &`-backgrounded GUI hangs the round-trip. Use
  `slicer vm bg exec … --shell=/bin/bash` with `setsid … </dev/null &`, or
  launch from the host when the display is on the host.
- `ffmpeg -t N` self-terminates; don't also kill it on a timer.
- Prompts typed via `send-keys` are eval'd by opencode: keep them free of
  unbalanced quotes (prefer no quotes at all in the prompt body).
- Model first-token latency is the main dead-lead-in source; the
  ffmpeg-before-Enter ordering plus the 3s buffer handles it.
- **Models do conservative inline `sleep`s.** Phrasing like "curl … until it
  returns 200" or a skill that says `sleep 8` nudges the agent into blind
  waits, which show up as a frozen pane mid-story (one model finished ~12s
  after the other purely from a long inline sleep). In the prompt, ask for a
  **status check over a blind wait** ("once the pod is Running, do a single
  curl") and keep any wait short. A per-pane MAD walk (split the frame at the
  pane divider, MAD each half) shows exactly which side went dead and when.
- If you DID start recording before prompting, trim the head to the first
  real body change instead.
