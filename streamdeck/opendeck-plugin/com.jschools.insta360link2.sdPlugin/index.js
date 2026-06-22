"use strict";

const WebSocket = require("ws");
const { spawn, execFile } = require("child_process");
const fs = require("fs");
const path = require("path");

const PLUGIN_UUID = "com.jschools.insta360link2";
const PREFIX = `${PLUGIN_UUID}.`;

/** Toggle actions: short name -> link-ctl status option */
const TOGGLES = new Set([
  "track",
  "deskview",
  "mirror",
  "whiteboard",
  "privacy",
  "hdr",
]);

/** @type {Record<string, { args?: string[], script?: string }>} */
const COMMANDS = {
  center: { args: ["center"] },
  normal: { args: ["normal"] },
  reset: { script: "reset.sh" },
  zoomin: { args: ["zoom-rel", "50"] },
  zoomout: { args: ["zoom-rel", "-50"] },
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

/** @type {Map<string, { short: string, context: string }>} */
const contexts = new Map();
const lastStateCache = new Map();
const lastTitleCache = new Map();

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

function linkCtlPaths() {
  const cfg = loadConfig();
  const linkCtl = resolveLinkCtl(cfg);
  if (!linkCtl) {
    return null;
  }
  return { cfg, linkCtl, python: resolvePython(cfg) };
}

function runLinkCtl(cliArgs, callback) {
  const paths = linkCtlPaths();
  if (!paths) {
    console.error("link_ctl.py not found — re-run streamdeck/opendeck-plugin/install.sh");
    callback(new Error("link_ctl not found"));
    return;
  }
  const env = { ...process.env, LINK_CTL_QUIET: "1" };
  execFile(
    paths.python,
    [paths.linkCtl, "--quiet", ...cliArgs],
    { env, timeout: 15000, maxBuffer: 4096 },
    (err, stdout) => {
      callback(err, stdout ? stdout.trim() : "");
    }
  );
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

  const paths = linkCtlPaths();
  if (!paths) {
    console.error("link_ctl.py not found — re-run streamdeck/opendeck-plugin/install.sh");
    return;
  }

  spawn(paths.python, [paths.linkCtl, "--quiet", ...spec.args], {
    stdio: "ignore",
    env,
  });
}

function send(obj) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

function setTitle(context, title) {
  if (lastTitleCache.get(context) === title) {
    return;
  }
  lastTitleCache.set(context, title);
  send({
    event: "setTitle",
    context,
    payload: { title, target: 0 },
  });
}

function setState(context, state) {
  if (lastStateCache.get(context) === state) {
    return;
  }
  lastStateCache.set(context, state);
  send({
    event: "setState",
    context,
    payload: { state },
  });
}

function applyToggleFeedback(context, isOn) {
  const state = isOn ? 1 : 0;
  setState(context, state);
  setTitle(context, isOn ? "ON" : "OFF");
}

function refreshToggleState(context, option) {
  runLinkCtl(["status", option, "--json", "-q"], (err, stdout) => {
    if (err && !stdout) {
      return;
    }
    try {
      const result = JSON.parse(stdout);
      if (typeof result.is_on === "boolean") {
        applyToggleFeedback(context, result.is_on);
      }
    } catch {
      // Camera unplugged or status unavailable — leave current state.
    }
  });
}

function handleToggle(short, context) {
  runLinkCtl([short, "toggle"], (err) => {
    if (err) {
      console.error(`toggle ${short}: ${err.message}`);
    }
    refreshToggleState(context, short);
  });
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

  switch (event) {
    case "willAppear": {
      const short = actionShort(action);
      if (!short) {
        break;
      }
      contexts.set(context, { short, context });
      if (TOGGLES.has(short)) {
        refreshToggleState(context, short);
      } else {
        setTitle(context, "");
      }
      break;
    }

    case "willDisappear":
      contexts.delete(context);
      lastStateCache.delete(context);
      lastTitleCache.delete(context);
      break;

    case "keyDown":
    case "dialDown":
    case "touchTap": {
      const short = actionShort(action);
      if (!short) {
        break;
      }
      if (TOGGLES.has(short)) {
        handleToggle(short, context);
      } else {
        runCommand(short);
      }
      break;
    }

    default:
      break;
  }
});

ws.on("close", () => process.exit(0));
ws.on("error", (err) => {
  console.error(err.message);
  process.exit(1);
});

process.on("SIGINT", () => process.exit(0));
process.on("SIGTERM", () => process.exit(0));
