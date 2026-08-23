#!/usr/bin/env python3
"""Trim a terminal-recording take by pixel-diff MAD over the body region.

Full-frame MD5/hash trimming is wrong for terminal video: a blinking cursor
or status-bar clock flips the hash every second while the story is frozen.
This uses per-frame mean absolute difference (MAD) of the luma plane,
excluding the bottom status strip, computed by ffmpeg itself
(signalstats YDIF) — no numpy, no PIL, nothing beyond ffmpeg on PATH.

Usage:
  mad_trim.py IN.mp4                 # report: profile, dead runs, suggested cut
  mad_trim.py IN.mp4 OUT.mp4         # apply the suggested cut and re-verify
  mad_trim.py IN.mp4 OUT.mp4 --start 17 --duration 107   # explicit cut
  mad_trim.py IN.mp4 --split-lr      # per-pane report for a two-up race
  mad_trim.py IN.mp4 QW.mp4 --rect 955,0,965,1040 --crop # one agent's clip

Options:
  --fps N          sample rate for the MAD walk (default 1)
  --body-bottom N  pixels excluded at the bottom (status strip, default 40)
  --real F         MAD threshold for a "real" story change (default 0.5)
  --dead F         MAD threshold below which a frame is "frozen" (default 0.01)
  --lead N         seconds kept before the first real change (default 3)
  --tail N         seconds held after the last real change (default 3)
  --crf N          x264 CRF for the re-encode (default 23, matching capture —
                   a lower value than the source makes the file BIGGER)
  --rect X,Y,W,H   restrict MAD to this region (e.g. one pane of a race)
  --crop           with --rect and OUT: crop the output to the rect too
  --split-lr       report left/right halves separately (two-up recordings)

Exit codes: 0 ok, 1 no real change found, 2 usage/ffmpeg error.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile


def probe_size(src):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", src],
        capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.split(",")[:2]
    return int(w), int(h)


def mad_profile(src, fps, rect):
    """One ffmpeg pass: crop to the region, per-frame luma MAD via
    signalstats YDIF, parsed from the metadata printer. Returns
    [(seconds, mad)] for every sampled frame after the first."""
    x, y, w, h = rect
    with tempfile.NamedTemporaryFile(mode="r", suffix=".txt", delete=False) as tmp:
        meta = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             "-vf", (f"fps={fps},crop={w}:{h}:{x}:{y},format=gray,signalstats,"
                     f"metadata=mode=print:file={meta}:key=lavfi.signalstats.YDIF"),
             "-f", "null", "-"],
            check=True)
        rows = []
        t = None
        with open(meta) as f:
            for line in f:
                if m := re.search(r"pts_time:([0-9.]+)", line):
                    t = float(m.group(1))
                elif m := re.search(r"lavfi\.signalstats\.YDIF=([0-9.]+)", line):
                    if t is not None and t > 0:
                        rows.append((t, float(m.group(1))))
        return rows
    finally:
        os.unlink(meta)


def analyse(rows, real, dead):
    first = next((t for t, m in rows if m > real), None)
    last = max((t for t, m in rows if m > real), default=None)
    runs, run = [], []
    for t, mad in rows:
        if mad < dead:
            run.append(t)
        else:
            if len(run) >= 2:
                runs.append((run[0], run[-1]))
            run = []
    if len(run) >= 2:
        runs.append((run[0], run[-1]))
    return first, last, runs


def report(label, rows, first, last, runs, lead, tail):
    prefix = f"[{label}] " if label else ""
    print(f"{prefix}frames sampled: {len(rows) + 1}")
    print(f"{prefix}first real change: t={first}s")
    print(f"{prefix}last  real change: t={last}s")
    print(f"{prefix}dead runs (>=2s):")
    for a, b in runs:
        print(f"{prefix}  t={a:.0f}..{b:.0f}  ({b - a:.0f}s)")
    if first is None:
        return None
    start = max(0, first - lead)
    dur = (last + tail) - start
    print(f"{prefix}suggested cut: -ss {start:.0f} -t {dur:.0f}  (lead {lead}s, tail {tail}s)")
    return start, dur


def apply_cut(src, dst, start, dur, crf, crop_rect):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", str(dur),
           "-i", src]
    if crop_rect:
        x, y, w, h = crop_rect
        w -= w % 2  # libx264 needs even dimensions
        h -= h % 2
        cmd += ["-vf", f"crop={w}:{h}:{x}:{y}"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", str(crf),
            "-pix_fmt", "yuv420p", dst]
    subprocess.run(cmd, check=True)
    in_mb = os.path.getsize(src) / 1e6
    out_mb = os.path.getsize(dst) / 1e6
    print(f"wrote {dst} ({start:.0f}s + {dur:.0f}s, {out_mb:.1f}MB vs {in_mb:.1f}MB source)")
    if out_mb > in_mb:
        print(f"warning: output is LARGER than the source — the re-encode CRF "
              f"({crf}) is higher quality than the capture; try a higher --crf",
              file=sys.stderr)


def parse_rect(spec):
    try:
        x, y, w, h = (int(v) for v in spec.split(","))
        return x, y, w, h
    except ValueError:
        sys.exit(f"bad --rect {spec!r}: want X,Y,W,H")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src", metavar="IN.mp4")
    ap.add_argument("out", nargs="?", metavar="OUT.mp4")
    ap.add_argument("--fps", type=float, default=1)
    ap.add_argument("--body-bottom", type=int, default=40)
    ap.add_argument("--real", type=float, default=0.5)
    ap.add_argument("--dead", type=float, default=0.01)
    ap.add_argument("--lead", type=float, default=3)
    ap.add_argument("--tail", type=float, default=3)
    ap.add_argument("--start", type=float)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--crf", type=int, default=23)
    ap.add_argument("--rect", metavar="X,Y,W,H")
    ap.add_argument("--crop", action="store_true")
    ap.add_argument("--split-lr", action="store_true")
    a = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH")
    if not os.path.isfile(a.src):
        sys.exit(f"no such file: {a.src}")

    width, height = probe_size(a.src)
    body_h = height - a.body_bottom

    if a.split_lr:
        half = width // 2
        for label, rect in (("left", (0, 0, half, body_h)),
                            ("right", (half, 0, width - half, body_h))):
            rows = mad_profile(a.src, a.fps, rect)
            first, last, runs = analyse(rows, a.real, a.dead)
            report(label, rows, first, last, runs, a.lead, a.tail)
        return 0

    rect = parse_rect(a.rect) if a.rect else (0, 0, width, body_h)
    rows = mad_profile(a.src, a.fps, rect)
    if len(rows) < 2:
        sys.exit("not enough frames sampled")
    first, last, runs = analyse(rows, a.real, a.dead)
    suggested = report(None, rows, first, last, runs, a.lead, a.tail)

    if a.out is None:
        return 0 if suggested is not None else 1

    if a.start is not None and a.duration is not None:
        start, dur = a.start, a.duration
        print(f"using explicit cut: -ss {start} -t {dur}")
    elif suggested is not None:
        start, dur = suggested
    else:
        print("no real change found — nothing to cut", file=sys.stderr)
        return 1

    crop_rect = parse_rect(a.rect) if (a.crop and a.rect) else None
    apply_cut(a.src, a.out, start, dur, a.crf, crop_rect)

    print("--- re-verify on the cut ---")
    v_w, v_h = probe_size(a.out)
    rows = mad_profile(a.out, a.fps, (0, 0, v_w, v_h - (0 if crop_rect else a.body_bottom)))
    first, last, runs = analyse(rows, a.real, a.dead)
    print(f"first real change: t={first}s")
    print(f"last  real change: t={last}s")
    print(f"dead runs (>=2s): {[(round(x), round(y)) for x, y in runs]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
