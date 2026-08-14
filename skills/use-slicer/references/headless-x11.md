# Headless X11 in Slicer

Run graphical applications, capture terminal output as video, or drive a
display server in Slicer for Mac and Slicer for Linux without a physical
monitor. Works identically on both platforms — the VM is the display host.

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
  "DISPLAY=:99 xterm -bg black -fg '#d4d4d4' -fs 14 \
     -geometry 100x35 -e bash &"
```

Key flags:

- `-fs 14` — scalable font size (preferred over `-fn` for reliability)
- `-geometry COLSxROWS` — terminal size

If text renders blank, the font name didn't resolve. Use `-fs` alone,
without `-fn`:

```bash
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "DISPLAY=:99 xterm -bg black -fg '#d4d4d4' -fs 14 -geometry 100x35 -e bash &"
```

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
  "DISPLAY=:99 xterm -bg black -fg '#d4d4d4' -fs 14 -geometry 100x35 \
     -e bash -c 'echo Recording started; sleep 30' & \
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

## Common issues

| Problem | Fix |
|---------|-----|
| Blank xterm, no text | Use `-fs 14` instead of `-fn`; ensure `fonts-dejavu-core` is installed |
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