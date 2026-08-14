import { writeFile } from "node:fs/promises";

const [targetUrl, domPath = "/tmp/page.dom.html", pngPath = "/tmp/page.png"] =
  process.argv.slice(2);
const endpoint = process.env.FIREFOX_BIDI_URL || "ws://127.0.0.1:9222/session";

if (!targetUrl) {
  console.error("Usage: node firefox-bidi.mjs URL [DOM_PATH] [PNG_PATH]");
  process.exit(2);
}

const socket = new WebSocket(endpoint);
const pending = new Map();
let nextId = 1;

socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.id === undefined) {
    return;
  }

  const request = pending.get(message.id);
  if (!request) {
    return;
  }

  pending.delete(message.id);
  if (message.type === "error") {
    request.reject(new Error(`${message.error}: ${message.message}`));
    return;
  }
  request.resolve(message.result);
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

function command(method, params) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

try {
  const session = await command("session.new", { capabilities: {} });
  const created = await command("browsingContext.create", { type: "tab" });
  const context = created.context;

  await command("browsingContext.navigate", {
    context,
    url: targetUrl,
    wait: "complete",
  });

  const evaluated = await command("script.evaluate", {
    expression: "document.documentElement.outerHTML",
    target: { context },
    awaitPromise: true,
    resultOwnership: "none",
  });
  const screenshot = await command("browsingContext.captureScreenshot", {
    context,
  });

  await writeFile(domPath, evaluated.result.value, "utf8");
  await writeFile(pngPath, Buffer.from(screenshot.data, "base64"));

  console.log(`browser=${session.capabilities.browserName}`);
  console.log(`version=${session.capabilities.browserVersion}`);
  console.log(`dom=${domPath}`);
  console.log(`screenshot=${pngPath}`);

  await command("session.end", {});
} finally {
  socket.close();
}
