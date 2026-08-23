# Headless X11 in Slicer

Run graphical applications, capture terminal output as video, or drive a
display server in Slicer for Mac and Slicer for Linux without a physical
monitor. Works identically on both platforms — the VM is the display host.

For the full agent-demo recording workflows, use the dedicated skills:

- **`use-xvfb-terminal-recording`** — record a terminal/TUI (coding agent)
  demo inside a single VM, with the clean ordering, MAD trimming, and
  delivery flow (ships `scripts/mad_trim.py`).
- **`use-dual-terminal-race`** — two agents in two fresh VMs, each bridged
  into a host xterm on a host Xvfb display, recorded as one video.

This reference covers the low-level primitives those skills build on.

## Minimal packages

```bash
slicer vm exec "$VM_NAME" --uid 0 -- \
  "DEBIAN_FRONTEND=noninteractive apt-get update && \
   DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     xvfb xterm fonts-dejavu-core"
```

Three packages: `xvfb` (virtual framebuffer), `xterm` (terminal client),
`fonts-dejavu-core` (monospace font for readable text).

For screen capture add `ffmpeg`:

```bash
slicer vm exec "$VM_NAME" --uid 0 -- \
  "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg"
```

## Starting Xvfb

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset & \
   export DISPLAY=:99"
```

Flags:

- `-screen 0 WIDTHxHEIGHTxDEPTH` — virtual screen dimensions
- `-ac` — disable access control (simplifies local use)
- `+extension GLX +render` — enable GLX and Render extensions
- `-noreset` — don't reset display between clients

For a one-shot command, use `xvfb-run` instead:

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "xvfb-run xterm -e bash -c 'echo hello; sleep 5'"
```

## Running xterm

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "DISPLAY=:99 xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
     -geometry 100x35 -e bash &"
```

Key flags:

- `-fa 'DejaVu Sans Mono'` — fontconfig face name; **must be paired with
  `-fs`**. `-fs` alone leaves xterm on its tiny fallback VGA font
  (~6px/char) and the capture is unreadable.
- `-fs 14` — scalable font size (preferred over `-fn`)
- `-geometry COLSxROWS` — terminal size

If text renders blank or tiny, the font did not resolve: use
`-fa 'DejaVu Sans Mono' -fs 14` together, with `fonts-dejavu-core`
installed.

## Capturing with ffmpeg

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "DISPLAY=:99 ffmpeg -f x11grab -video_size 1920x1080 -i :99.0 \
     -framerate 25 -c:v libx264 -preset fast -pix_fmt yuv420p \
     output.mp4"
```

To capture for a fixed duration:

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "DISPLAY=:99 ffmpeg -f x11grab -video_size 1920x1080 -i :99.0 \
     -framerate 25 -t 60 -c:v libx264 -preset fast -pix_fmt yuv420p \
     output.mp4"
```

## Full example — record a terminal session

```bash
# Start Xvfb
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "Xvfb :99 -screen 0 1280x720x24 -ac & \
   export DISPLAY=:99; sleep 1"

# Launch xterm with a command
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "DISPLAY=:99 xterm -bg black -fg '#d4d4d4' -fa 'DejaVu Sans Mono' -fs 14 \
     -geometry 100x35 -e bash -c 'echo Recording started; sleep 30' & \
   sleep 2"

# Capture
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "DISPLAY=:99 ffmpeg -f x11grab -video_size 1280x720 -i :99.0 \
     -framerate 25 -t 30 -c:v libx264 -preset fast -pix_fmt yuv420p \
     /tmp/recording.mp4"

# Copy out
slicer vm cp "$VM_NAME":/tmp/recording.mp4 ./recording.mp4

# Cleanup
slicer vm exec "$VM_NAME" --uid 1000 -- "killall xterm Xvfb"
```

## Recording an interactive TUI (coding agent) demo — the clean way

This extends the pattern above for a two-pane `tmux + opencode` demo, the
case the simple example does not cover. Verified on `e2e-8` 2026-08-14.

Worked recipe (mirrors `docs/record-demo.sh` in the superterm repo):

1. Give each pane its own tmux **session** (not two panes of one session) so
   tools that address agents by session (e.g. superterm mail) work:

   ```bash
   slicer vm exec "$VM_NAME" --uid 1000 -- \
     "tmux new-session -d -s teacher -x 73 -y 41 && \
      tmux new-session -d -s student -x 72 -y 41"
   ```

2. Launch the agent in each with permission auto-approval. opencode's flag is
   `--auto`; Claude Code uses `--dangerously-skip-permissions`. **Without it
   the agent locks on "⚠ Permission required … Allow once / Allow always /
   Reject" and the whole demo stalls** (an external-directory `/etc/*` prompt
   even snuck past config-based auto-allow):

   ```bash
   slicer vm exec "$VM_NAME" --uid 1000 -- \
     "tmux send-keys -t teacher 'opencode --auto' Enter; \
      tmux send-keys -t student 'opencode --auto' Enter"
   ```

3. Wait for the TUIs to draw their splash before doing anything visible.
4. Attach xterms to each session, side by side, on one Xvfb display.
   **Two separate xterms (one per session) at 73+73 cols** gives the
   side-by-side pairup without nested tmux:
   `-geometry 73x41+0+0` and `-geometry 73x41+955+0` on a 1920x1080 screen.
5. **Start ffmpeg x11grab now** — after the splash, before the prompts — so
   frame one is the fresh splash, not a progressed session.
6. Send the role/task prompts via `tmux send-keys`. Staggering the two
   sides is optional — simultaneous reads fine.
7. MAD-scan frames (not MD5) to find the last content change and trim the
   dead tail before shipping (see "Trim before shipping" below).
8. Serve behind an `index.html` through an inlets tunnel so the URL is stable
   across revisions:
   `python3 -m http.server 8300 &` + `inlets-pro uplink client --upstream=<domain>=http://127.0.0.1:8300`.

### Trim before shipping

A 300s take can be ~80% idle after the exchange completes, which reads as
"stuck". **Do not trim by full-frame MD5** — a blinking cursor or the
status-bar clock flips the hash every second while the story is frozen
(learned the hard way: MD5 showed "118/120 unique" on a take that was
actually static from frame 15). Use per-pixel mean absolute difference
(MAD) over the body region (exclude the bottom ~40px status strip):
`mad > 0.5` = real change, `mad < 0.01` = frozen. Find the first and last
real change, keep a ~3s buffer before and after, and re-encode:

```bash
# the use-xvfb-terminal-recording skill ships the tool:
#   scripts/mad_trim.py IN.mp4 [OUT.mp4] [--lead N] [--tail N]
# report only:
python3 scripts/mad_trim.py in.mp4
# apply the suggested cut and re-verify:
python3 scripts/mad_trim.py in.mp4 out.mp4
```

If you must do it by hand: extract 1 fps grayscale frames, compute
`numpy |frame - prev|.mean()` over `im[:h-40, :]`, find the last `t` with
MAD > 0.5, then `ffmpeg -y -ss 0 -t <t+5> -i in.mp4 -c:v libx264 -preset
fast -crf 20 -pix_fmt yuv420p out.mp4`.

### Gotchas specific to this pattern

- **Font:** xterm needs `-fa 'DejaVu Sans Mono' -fs 15`. `-fs` alone resolves
  to xterm's tiny fallback VGA font (~6px/char) and the capture is
  unreadable. `fonts-dejavu-core` must be installed in the VM.
- **Even dimensions:** x264 refuses odd heights ("height not divisible by
  2"). Window may be 1902x1029; capture at 1902x1028, 1904x1028, etc.
- **`setsid` + `</dev/null &`** inside `slicer vm bg exec` so the GUI/ffmpeg
  survives the client round-trip; do not also background with `& disown` then
  expect exec to return.
- **`pkill tmux` kills every session on the server** — including unrelated
  long-lived demo sessions. Kill only what you mean
  (`tmux kill-session -t X`).
- Small scripts and prompts should be staged locally and `slicer vm cp`'d in,
  rather than multi-line `send-keys` (see interactive-tui.md).
```

## Common issues

| Problem | Fix |
|---------|-----|
| Blank xterm, no text | Use `-fa 'DejaVu Sans Mono' -fs 14` (not `-fs` alone, not `-fn`); ensure `fonts-dejavu-core` is installed |
| `xterm: unable to open font` | Xvfb font path not loaded; use `-fs` scalable font instead |
| ffmpeg `Cannot connect to X server` | `DISPLAY` not set, or Xvfb not running |
| Black video, no content | xterm hasn't drawn yet; add `sleep 2` after launching xterm |
| `xvfb: cannot connect to MIT-MAGIC-COOKIE` | Pass `-ac` flag to disable access control |

## Alternatives to X11

- **`tmux capture-pane` + Pillow** — pure headless, no X at all; renders
  terminal text to images with Python, then stitches with ffmpeg.
- **`ttyrec` + `ttyplay`** — records terminal escape sequences for playback;
  replay into Xvfb + xterm for video capture.
- **`xvfb-run`** — one-shot wrapper that starts Xvfb, runs a command, and
  cleans up: `xvfb-run xterm -e bash -c 'sleep 10'`.