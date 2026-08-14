# Headless browser and DOM rendering

Use a real browser when a task needs JavaScript execution, DOM/layout fidelity,
or screenshot evidence inside a SlicerVM. Keep browser installations in a
disposable VM unless they are intentionally part of a reusable image.

## Choose the smallest suitable route

| Route | Clean disk delta | Use when |
|---|---:|---|
| Official Firefox + WebDriver BiDi | 378.8 MiB | Engine-neutral DOM and screenshot evidence; lean default |
| Playwright Chromium headless shell + minimal libraries | 544.8 MiB | Chromium-specific rendering or direct `--dump-dom` |
| Playwright Chromium + `install-deps` | 651.0 MiB | Convenience matters more than footprint |

These figures were measured in fresh Ubuntu 24.04 arm64 SlicerVMs on
2026-08-08, after removing apt indexes and npm caches. Browser versions,
distribution packages, and architectures will change the result.

Do not select `wkhtmltoimage` merely because it is smaller. Version 0.12.6
added 325.8 MiB in the same test, but failed modern JavaScript syntax, and its
upstream project is archived. It is not a comparable modern-browser result.

## Lean default: official Firefox

Install Mozilla's official arm64 build as the guest user and only its required
Ubuntu runtime libraries. The Mozilla redirect selects the current stable
release:

```bash
slicer vm exec "$VM_NAME" --uid 1000 --cwd /home/ubuntu \
  --env HOME=/home/ubuntu -- \
  "curl -fsSL \
     'https://download.mozilla.org/?product=firefox-latest&os=linux64-aarch64&lang=en-US' \
     -o /tmp/firefox.tar.xz && \
   tar -xJf /tmp/firefox.tar.xz && rm /tmp/firefox.tar.xz"

slicer vm exec "$VM_NAME" --uid 0 -- \
  "DEBIAN_FRONTEND=noninteractive apt-get update && \
   DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     libgtk-3-0t64 libasound2t64 fonts-liberation libx11-xcb1"
```

For x86-64, change `linux64-aarch64` to `linux64`. Package names above are for
Ubuntu 24.04; inspect `ldd /home/ubuntu/firefox/firefox` and use the local
distribution's equivalent packages elsewhere.

For a screenshot with an exact viewport, Firefox's CLI is enough:

```bash
URL=http://127.0.0.1:8080/

slicer vm exec "$VM_NAME" --uid 0 -- \
  "install -d -o 1000 -g 1000 /tmp/firefox-profile"

slicer vm exec "$VM_NAME" --uid 1000 --cwd /home/ubuntu -- \
  "env -u DISPLAY MOZ_HEADLESS=1 MOZ_WEBRENDER=0 LIBGL_ALWAYS_SOFTWARE=1 \
     /home/ubuntu/firefox/firefox \
       --headless --no-remote --profile /tmp/firefox-profile \
       --window-size 1280,720 --screenshot /tmp/page.png '$URL'"

slicer vm cp "$VM_NAME":/tmp/page.png ./page.png
```

Firefox's CLI does not have a `--dump-dom` switch. For both the post-JavaScript
DOM and a screenshot, run its built-in WebDriver BiDi server on loopback and
use the bundled Node client. Slicer base images already contain Node; check
`node --version` before relying on this route in a custom image.

```bash
slicer vm cp skills/use-slicer/scripts/firefox-bidi.mjs \
  "$VM_NAME":/tmp/firefox-bidi.mjs --uid 1000

slicer vm bg exec "$VM_NAME" --uid 1000 --cwd /home/ubuntu \
  --shell=/bin/bash -- \
  "mkdir -p /tmp/firefox-profile && \
   env -u DISPLAY MOZ_HEADLESS=1 MOZ_WEBRENDER=0 LIBGL_ALWAYS_SOFTWARE=1 \
     /home/ubuntu/firefox/firefox \
       --headless --no-remote --profile /tmp/firefox-profile \
       --remote-debugging-port 9222 about:blank"

# Wait until the background logs contain the ws://127.0.0.1:9222/session URL.
slicer vm exec "$VM_NAME" --uid 1000 -- \
  "node /tmp/firefox-bidi.mjs \
     'http://127.0.0.1:8080/' /tmp/page.dom.html /tmp/page.png"

slicer vm cp "$VM_NAME":/tmp/page.png ./page.png
slicer vm cp "$VM_NAME":/tmp/page.dom.html ./page.dom.html
```

The script ends the BiDi session, but Firefox may keep the dedicated browser
process alive. Check `slicer vm bg info`, kill it if it remains running, then
remove the completed background record. The debugging endpoint has no
authentication, so leave it bound to loopback and do not port-forward it.

## Chromium-specific route

Install the headless shell as the guest user:

```bash
slicer vm exec "$VM_NAME" --uid 1000 --cwd /home/ubuntu \
  --env HOME=/home/ubuntu -- \
  "npx --yes playwright install chromium-headless-shell"
```

For the lean variant, inspect the downloaded binary with `ldd` and install only
the missing libraries. For Playwright headless shell 151.0.7922.34 on Ubuntu
24.04 arm64, this tested set was sufficient:

```bash
slicer vm exec "$VM_NAME" --uid 0 -- \
  "DEBIAN_FRONTEND=noninteractive apt-get update && \
   DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     libnspr4 libnss3 libatk1.0-0t64 libx11-6 libxcomposite1 \
     libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libxcb1 \
     libxkbcommon0 libasound2t64 libatspi2.0-0t64 fonts-liberation"
```

For a broader, version-tolerant installation, use Playwright's dependency
installer instead. It installs substantially more packages, including Xvfb:

```bash
slicer vm exec "$VM_NAME" --uid 0 --cwd /root \
  --env DEBIAN_FRONTEND=noninteractive -- \
  "npx --yes playwright install-deps chromium"
```

Render both outputs directly:

```bash
URL=http://127.0.0.1:8080/

slicer vm exec "$VM_NAME" --uid 1000 -- \
  "BROWSER=\$(find /home/ubuntu/.cache/ms-playwright \
      -type f -path '*/chrome-linux/headless_shell' -print -quit); \
   test -n \"\$BROWSER\"; \
   env -u DISPLAY \"\$BROWSER\" \
      --headless --no-sandbox --disable-gpu \
      --window-size=1280,720 \
      --dump-dom --screenshot=/tmp/page.png \
      '$URL' > /tmp/page.dom.html"

slicer vm cp "$VM_NAME":/tmp/page.png ./page.png
slicer vm cp "$VM_NAME":/tmp/page.dom.html ./page.dom.html
```

`--no-sandbox` refers to Chromium's process sandbox. Use it only inside the
already isolated disposable VM. GPU, Vulkan, EGL, or VAAPI warnings are normal
without a GPU; judge success by the exit status and output files.

## Clean and measure

Reclaim transient data while retaining the browser and runtime libraries:

```bash
slicer vm exec "$VM_NAME" --uid 0 -- \
  "rm -rf /home/ubuntu/.npm /root/.npm /var/lib/apt/lists/*"
```

When measuring an installation with timestamp markers, do not trust only
`find -newer`: apt packages preserve archive mtimes, so it undercounts newly
created files. Keep the requested mtime result, but use ctime and filesystem
usage for the defensible delta:

```bash
touch /tmp/before
# perform installation
sync
touch /tmp/after

# mtime window: useful, but apt package contents may be missed
find / -xdev -type f -newer /tmp/before ! -newer /tmp/after -printf '%b\n'

# ctime window: captures newly extracted package files
find / -xdev -type f -cnewer /tmp/before ! -cnewer /tmp/after -printf '%b\n'

# compare this before and after as the filesystem-level cross-check
df -B1 --output=used /
```

Sum `%b` values and multiply by 512 for allocated bytes. Use `%s` instead when
apparent file size is required.
