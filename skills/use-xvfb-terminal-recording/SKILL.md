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

### Two shells side by side — prefer one split session

The per-session layout above is for **agent** demos, where tools address
each agent by session name. For a plain **two-shell** split screen (a
service on the left, a client driving it on the right) use ONE session
with two panes instead, and one wide xterm:

```bash
tmux new-session -d -s demo -x 200 -y 50
tmux split-window -h -t demo
tmux setw -t demo synchronize-panes off   # ensure keystrokes are NOT mirrored
# address panes by explicit session:window.pane, and verify they are
# independent BEFORE recording:
tmux send-keys -t demo:0.0 'AAA'; tmux send-keys -t demo:0.1 'BBB'
tmux capture-pane -t demo:0.0 -p | tail -1   # must show AAA only
tmux capture-pane -t demo:0.1 -p | tail -1   # must show BBB only
```

Use the full `session:window.pane` target (`demo:0.0`, not `demo.0`) — the
colon-less form is parsed as a window in the current session and can miss
the pane you created.

Why: two separate sessions each attached by its own xterm can end up
receiving **every** keystroke on **both** — `send-keys -t left` lands in
`right` too, so both composers fill with both commands. A single split
session sidesteps it and needs only one xterm. Always send distinct
markers and `capture-pane` each target before you record; never trust
that `-t left`/`-t right` are isolated.

- opencode: `--auto` auto-approves permission prompts. **Without it the
  agent locks on "⚠ Permission required … Allow once / Allow always /
  Reject" and the demo stalls.** (Equivalent to Claude Code's
  `--dangerously-skip-permissions`.) Pin the model explicitly with `-m` for
  tests — do not rely on the config default.
- Wait for the splash, then confirm with
  `tmux capture-pane -t left -p | tail -5` (shows `~  ...  <version>`).

## Step 3 — xterms on the display

**Per-agent `left`/`right` layout** — one xterm per session:

```bash
DISPLAY=:99 setsid xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
  -geometry 73x41+0+0 -e tmux attach -t left </dev/null >/dev/null 2>&1 &
DISPLAY=:99 setsid xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
  -geometry 73x41+955+0 -e tmux attach -t right </dev/null >/dev/null 2>&1 &
```

**Split-session two-shell layout (Step 2)** — one wide xterm attached to the
single `demo` session; the internal `split-window` divider is the visual gap:

```bash
DISPLAY=:99 setsid xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 13 \
  -geometry 200x50+0+0 -e tmux attach -t demo </dev/null >/dev/null 2>&1 &
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

**Commands with quotes or JSON: send a script, not the literal.** A
`send-keys` string like a `curl … -d '{"cmd":"…"}'` is re-quoted by your
shell, then by the remote `slicer vm exec`, then by tmux — unbalanced
quotes and `EOF while looking for matching '` are near-certain. Write the
whole client sequence to a `demo.sh`, copy it into the VM, and
`send-keys -t demo:0.1 './demo.sh'`. The composer shows one clean command
and there is nothing to mis-quote.

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

### Dead *middle*: splice it out with a concat, not a single cut

`mad_trim.py` does one `-ss/-t` window, so it cannot remove a frozen gap in
the middle — e.g. a service starts, then you wait for it to warm up before
the client fires, leaving 10s+ of static split-screen. When the dead-run
report shows a middle gap `(A, B)`, cut the two live spans and concat them:

```bash
ffmpeg -y -i raw.mp4 -ss 0  -t A       -c:v libx264 -preset fast -pix_fmt yuv420p seg1.mp4
ffmpeg -y -i raw.mp4 -ss B  -t DUR_B   -c:v libx264 -preset fast -pix_fmt yuv420p seg2.mp4   # DUR_B = end - B
printf 'file seg1.mp4\nfile seg2.mp4\n' > concat.txt
ffmpeg -y -f concat -i concat.txt -c copy final.mp4
python3 scripts/mad_trim.py final.mp4   # re-verify: dead runs should be empty
```

Better still, avoid the gap at capture time: poll the readiness endpoint
(not a blind `sleep`) and trigger the client the instant it is ready.

## Step 7 — Deliver

Serve a page, not a raw file, through one tunnel so the URL stays stable as
revisions are swapped. **Do NOT use `python3 -m http.server` for video** —
its stdlib handler ignores `Range` headers and always returns `200` with
the whole file, so the browser cannot seek to any byte it has not already
buffered (scrubbing ahead is dead). Use a range-capable server such as
`inlets-pro fileserver`, which answers `206 Partial Content`:

```bash
# range-capable static server on 127.0.0.1:8300
inlets-pro fileserver --webroot /tmp/opencode --port 8300 -a &
inlets-pro cloud create <name>
inlets-pro uplink client --url=wss://.../<name> --token=... \
  --upstream=<domain>=http://127.0.0.1:8300
```

- **`inlets-pro fileserver` concatenates `--port` onto `--data-addr`.**
  Passing both `--data-addr 127.0.0.1:8300` and `--port 8300` binds the
  bogus `83008300`. Use `--port 8300` alone and leave `--data-addr` (default
  `127.0.0.1:`) portless.
- **Re-mux each video with `+faststart`** so the `moov` atom sits at the
  front (ffmpeg writes it at the end by default), letting the player seek
  before the whole file downloads: `ffmpeg -i in.mp4 -c copy -movflags
  +faststart out.mp4`.
- **Back up the previous video and index.html before swapping.**
- Point `index.html`'s `<video src>` at the new file.
- Verify locally and publicly with a **deep ranged GET** — it must return
  `206`, not `200`: `curl -o /dev/null -w '%{http_code}\n' -r 300000-400000
  https://<domain>/take.mp4`.

## Gotchas

- **`pkill tmux` kills every session on the server** — kill by session name
  (`tmux kill-session -t X`).
- `slicer vm exec` with a `… &`-backgrounded GUI hangs the round-trip. Use
  `slicer vm bg exec … --shell=/bin/bash` with `setsid … </dev/null &`, or
  launch from the host when the display is on the host.
- `ffmpeg -t N` self-terminates; don't also kill it on a timer. **Never
  `pkill` the capture** — a killed x11grab leaves an mp4 with no moov atom
  (`ffprobe` fails, the file is unplayable and untrimmable). Size `-t` to
  the content plus a few seconds and let it end itself; check
  `ffprobe -show_entries stream=width,height` before trusting a take.
- **One take = one self-contained job.** Drive each recording (start
  ffmpeg → stage → Enter → wait for done) from a single command, not
  several overlapping background tasks. A completion task from a *previous*
  take that ends with `send-keys -t <pane> C-c` will fire mid-way through
  the next take and wipe its staged command, so you record an idle prompt.
  After staging, re-`capture-pane` to confirm the command is still there
  immediately before you press Enter.
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
