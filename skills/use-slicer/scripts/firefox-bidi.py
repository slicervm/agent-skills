"""WebDriver BiDi screenshot + DOM capture — Python stdlib only.

No Node.js or pip required. Uses the WebSocket subprotocol of Firefox's
Remote Debugging port (9222) to navigate, wait for full page load
(including images), and capture a screenshot.

Usage:
    python3 firefox-bidi.py URL [DOM_PATH] [PNG_PATH]

Requires Firefox running with --remote-debugging-port 9222 on loopback.
"""

import sys, json, base64, time, struct, os, socket

def ws_connect(url):
    if url.startswith("ws://"):
        url = url[5:]
    host, _, path = url.partition("/")
    path = "/" + path
    if ":" in host:
        hostname, port = host.rsplit(":", 1)
        port = int(port)
    else:
        hostname, port = host, 80

    sock = socket.create_connection((hostname, port))

    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(req.encode())

    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += sock.recv(4096)

    if b"101" not in resp.split(b"\r\n")[0]:
        raise Exception(f"WebSocket handshake failed: {resp[:200]}")

    return sock


def ws_send(sock, data):
    payload = data.encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

    header = bytearray([0x81])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack(">Q", length))
    header.extend(mask)
    sock.sendall(bytes(header) + masked)


def _recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise Exception("Connection closed")
        data += chunk
    return data


def ws_recv(sock):
    header = _recv_exact(sock, 2)
    opcode = header[0] & 0x0F
    masked = header[1] & 0x80
    length = header[1] & 0x7F

    if length == 126:
        length = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(sock, 8))[0]

    if masked:
        mask = _recv_exact(sock, 4)

    data = _recv_exact(sock, length)

    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))

    if opcode == 0x9:  # ping
        ws_send_raw(sock, 0xA, data)
        return ws_recv(sock)
    if opcode == 0xA:  # pong
        return ws_recv(sock)

    return data.decode("utf-8")


def ws_send_raw(sock, opcode, payload):
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack(">Q", length))
    header.extend(mask)
    sock.sendall(bytes(header) + masked)


# --- Main ---

target_url = sys.argv[1]
dom_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/page.dom.html"
png_path = sys.argv[3] if len(sys.argv) > 3 else "/tmp/page.png"
endpoint = "ws://127.0.0.1:9222/session"

next_id = 1

sock = ws_connect(endpoint)


def command(method, params=None):
    global next_id
    cid = next_id
    next_id += 1
    msg = {"id": cid, "method": method}
    if params is not None:
        msg["params"] = params
    ws_send(sock, json.dumps(msg))

    while True:
        data = ws_recv(sock)
        msg = json.loads(data)
        if msg.get("id") == cid:
            if msg.get("type") == "error":
                raise Exception(f"{msg.get('error')}: {msg.get('message')}")
            return msg.get("result", {})


session = command("session.new", {"capabilities": {}})
created = command("browsingContext.create", {"type": "tab"})
context = created["context"]

command("browsingContext.navigate", {
    "context": context,
    "url": target_url,
    "wait": "complete",
})

# Wait for images and lazy assets to finish loading.
# `wait: "complete"` waits for the DOM load event but not all
# image downloads; a short delay covers the gap.
time.sleep(3)

if dom_path:
    evaluated = command("script.evaluate", {
        "expression": "document.documentElement.outerHTML",
        "target": {"context": context},
        "awaitPromise": True,
        "resultOwnership": "none",
    })
    with open(dom_path, "w") as f:
        f.write(evaluated["result"]["value"])

screenshot = command("browsingContext.captureScreenshot", {"context": context})

with open(png_path, "wb") as f:
    f.write(base64.b64decode(screenshot["data"]))

print(f"browser={session.get('capabilities', {}).get('browserName', 'firefox')}")
print(f"dom={dom_path}")
print(f"screenshot={png_path}")

try:
    command("session.end", {"capabilities": {}})
except Exception:
    pass
sock.close()
