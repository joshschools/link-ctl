"use strict";

const WebSocket = require("ws");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const PLUGIN_UUID = "com.jschools.insta360link2";
const PREFIX = `${PLUGIN_UUID}.`;

/** @type {Record<string, { args?: string[], script?: string }>} */
const COMMANDS = {
  trackon: { args: ["track", "on"] },
  trackoff: { args: ["track", "off"] },
  deskviewon: { args: ["deskview", "on"] },
  deskviewoff: { args: ["deskview", "off"] },
  mirroron: { args: ["mirror", "on"] },
  center: { args: ["center"] },
  normal: { args: ["normal"] },
  reset: { script: "reset.sh" },
  zoomin: { args: ["zoom-rel", "50"] },
  zoomout: { args: ["zoom-rel", "-50"] },
  overheadon: { args: ["overhead", "on"] },
  overheadoff: { args: ["overhead", "off"] },
  whiteboardon: { args: ["whiteboard", "on"] },
  whiteboardoff: { args: ["whiteboard", "off"] },
  privacyon: { args: ["privacy", "on"] },
  privacyoff: { args: ["privacy", "off"] },
};

const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  args[process.argv[i].replace(/^-/, "")] = process.argv[i + 1];
}

const port = args.port;
const pluginUUID = args.pluginUUID;
const registerEvent = args.registerEvent;

if (!port || !pluginUUID || !registerEvent) {
  console.error("Missing required args: -port -pluginUUID -registerEvent");
  process.exit(1);
}

/** @returns {{ repoRoot?: string, linkCtlPath?: string, python?: string }} */
function loadConfig() {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(__dirname, "link-ctl-path.json"), "utf8")
    );
  } catch {
    return {};
  }
}

function resolvePython(cfg) {
  return (
    process.env.LINK_CTL_PYTHON ||
    cfg.python ||
    (fs.existsSync("/usr/bin/python3") ? "/usr/bin/python3" : "python3")
  );
}

function resolveLinkCtl(cfg) {
  if (process.env.LINK_CTL_PY) {
    return process.env.LINK_CTL_PY;
  }
  if (cfg.linkCtlPath && fs.existsSync(cfg.linkCtlPath)) {
    return cfg.linkCtlPath;
  }
  if (cfg.repoRoot) {
    const candidate = path.join(cfg.repoRoot, "link_ctl.py");
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function resolveRepoRoot(cfg) {
  if (cfg.repoRoot && fs.existsSync(cfg.repoRoot)) {
    return cfg.repoRoot;
  }
  const linkCtl = resolveLinkCtl(cfg);
  if (linkCtl) {
    return path.dirname(linkCtl);
  }
  return null;
}

function actionShort(action) {
  if (!action || !action.startsWith(PREFIX)) {
    return null;
  }
  return action.slice(PREFIX.length);
}

function runCommand(short) {
  const spec = COMMANDS[short];
  if (!spec) {
    console.error(`Unknown action: ${short}`);
    return;
  }

  const cfg = loadConfig();
  const env = { ...process.env, LINK_CTL_QUIET: "1" };

  if (spec.script) {
    const repoRoot = resolveRepoRoot(cfg);
    if (!repoRoot) {
      console.error("link-ctl repo not found — re-run streamdeck/opendeck-plugin/install.sh");
      return;
    }
    const scriptPath = path.join(repoRoot, "streamdeck", spec.script);
    spawn("bash", [scriptPath], { stdio: "ignore", env });
    return;
  }

  const linkCtl = resolveLinkCtl(cfg);
  if (!linkCtl) {
    console.error("link_ctl.py not found — re-run streamdeck/opendeck-plugin/install.sh");
    return;
  }

  const python = resolvePython(cfg);
  spawn(python, [linkCtl, "--quiet", ...spec.args], { stdio: "ignore", env });
}

function send(obj) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

const ws = new WebSocket(`ws://127.0.0.1:${port}`);

ws.on("open", () => {
  send({ event: registerEvent, uuid: pluginUUID });
  console.log(`Registered ${PLUGIN_UUID}`);
});

ws.on("message", (raw) => {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch {
    return;
  }

  const { event, action, context } = msg;
  if (event !== "keyDown" && event !== "dialDown" && event !== "touchTap") {
    return;
  }

  const short = actionShort(action);
  if (!short) {
    return;
  }

  runCommand(short);
});

ws.on("close", () => process.exit(0));
ws.on("error", (err) => {
  console.error(err.message);
  process.exit(1);
});

process.on("SIGINT", () => process.exit(0));
process.on("SIGTERM", () => process.exit(0));
