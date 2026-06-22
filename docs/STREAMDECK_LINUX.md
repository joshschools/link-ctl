# Stream Deck on Linux with link-ctl

Use link-ctl shell scripts to control an **Insta360 Link 2** on Linux without
Insta360's Windows/macOS-only Stream Deck plugin. Works with [Elgato Stream Deck
software on Linux](https://www.elgato.com/stream-deck) (6.x+) and any launcher
that can run a shell command.

## Prerequisites

```bash
sudo apt install v4l-utils libusb-1.0-0-dev python3
make -C tools uvc-probe-linux
sudo cp tools/99-insta360-link.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Verify USB control:

```bash
python3 tools/validate.py --backend usb   # expect 8/8 on Link 2
```

## Quick setup (Elgato Stream Deck)

1. Open **Stream Deck** → add a **System → Open** action (or **Multi Action**).
2. Set the command to a script, e.g.:
   ```
   /home/you/Projects/link-ctl/streamdeck/track_on.sh
   ```
3. Repeat for each button. Scripts resolve `link_ctl.py` relative to the repo —
   move the whole `link-ctl` directory freely.

### Alternative: run `link_ctl.py` directly

Command:
```bash
python3 /home/you/Projects/link-ctl/link_ctl.py --quiet track on
```

Use `--quiet` so Stream Deck does not capture informational stdout.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `LINK_CTL_QUIET` | `1` in scripts | Pass `--quiet` to link-ctl |
| `LINK_CTL_V4L2_DEVICE` | auto | Force `/dev/videoN` if needed |
| `LINK_CTL_PY` | `../link_ctl.py` | Override CLI path |

## Available scripts

| Script | Action |
|--------|--------|
| `center.sh` | Center pan/tilt, zoom 100 |
| `track_on.sh` / `track_off.sh` | AI tracking |
| `deskview_on.sh` / `deskview_off.sh` | DeskView |
| `whiteboard_on.sh` / `whiteboard_off.sh` | Whiteboard |
| `overhead_on.sh` / `overhead_off.sh` | Overhead view |
| `normal.sh` | Standard mode |
| `zoom_in.sh` / `zoom_out.sh` | Zoom ±50 |
| `hdr_on.sh` / `hdr_off.sh` | HDR |
| `mirror_on.sh` / `mirror_off.sh` | Horizontal flip |
| `autoexposure_toggle.sh` | Toggle AE |
| `awb_toggle.sh` | Toggle auto white balance |
| `privacy_on.sh` / `privacy_off.sh` | Link 2 gimbal-down privacy |

## Suggested 15-key layout

```
[ Track ON ] [ Track OFF ] [ Desk ON  ] [ Desk OFF ] [ Center   ]
[ WB ON    ] [ WB OFF    ] [ HDR ON   ] [ HDR OFF  ] [ Mirror   ]
[ Zoom +   ] [ Zoom -    ] [ Normal   ] [ Privacy  ] [ Overhead ]
```

Map **Privacy** to `privacy_on.sh` / `privacy_off.sh` (Link 2 only).

## OpenDeck (recommended on Linux)

[OpenDeck](https://github.com/nekename/OpenDeck) drives Elgato hardware on Linux.
link-ctl supports two integration styles:

| Approach | Profile | Dependency | Best for |
|----------|---------|------------|----------|
| **Native plugin** (recommended) | `Link2Plugin` | Node.js 20+ (`/bin/node`) | Drag actions from sidebar; no Starter Pack |
| **Starter Pack profile** | `Link2` | Starter Pack plugin | Legacy / no Node.js |

Both call the same `link_ctl.py` USB backend. The native plugin is a small Node.js
`.sdPlugin` (same format as PipeWire Audio Control) — no Rust compile step.

### Install native plugin + profile

Prerequisites: [OpenDeck](https://github.com/nekename/OpenDeck) 2.5+, Node.js 20+
at `/usr/bin/node` (OpenDeck looks there; symlink if you use nvm).

With the Stream Deck plugged in and OpenDeck running at least once:

```bash
cd ~/Projects/link-ctl
bash streamdeck/opendeck-plugin/install.sh
```

This copies `com.jschools.insta360link2.sdPlugin` to
`~/.config/opendeck/plugins/`, writes `link-ctl-path.json` with your repo path,
runs `npm install`, installs the **Link2Plugin** profile, and restarts OpenDeck.

Plugin-only (keep your existing layout):

```bash
bash streamdeck/opendeck-plugin/install.sh --no-profile
```

Then drag **Insta360 Link 2** actions from the OpenDeck action list onto keys.

### Install Starter Pack profile (legacy)

```bash
bash streamdeck/opendeck/install.sh
```

Uses **Run Command** actions → `streamdeck/*.sh`. Requires Starter Pack
(`com.amansprojects.starterpack.sdPlugin`).

### Select a profile

After install, the deck should load the new profile automatically. To switch later,
use the profile dropdown in OpenDeck, or:

```bash
opendeck --process-message '{
  "event": "switchProfile",
  "payload": {
    "device": "sd-A00SA5022NHZOS",
    "profile": "Link2Plugin"
  }
}'
```

Replace `sd-A00SA5022NHZOS` with your device id (`ls ~/.config/opendeck/profiles/`).
Use `"Link2"` for the Starter Pack profile.

### Regenerate after moving the repo

```bash
bash streamdeck/opendeck-plugin/install.sh
# or, profile only:
python3 tools/build_opendeck_plugin_profile.py --install
# Starter Pack profile:
python3 tools/build_opendeck_profile.py --install
```

The plugin stores your checkout path in `link-ctl-path.json` at install time.
Re-run `install.sh` after moving the repo.

### OpenDeck 15-key layout

```
[ Track    ] [ Track Off] [ Desk     ] [ Desk Off ] [ Center   ]
[ Overhead ] [ Over Off ] [ Board    ] [ Board Off] [ Mirror   ]
[ Zoom +   ] [ Zoom −   ] [ Reset    ] [ Privacy  ] [ Priv Off ]
```

### Plugin development

Source: `streamdeck/opendeck-plugin/com.jschools.insta360link2.sdPlugin/`

- `manifest.json` — action UUIDs (Stream Deck SDK format)
- `index.js` — WebSocket handler; spawns `link_ctl.py --quiet …` on key press
- `CodePathLin: index.js` — interpreted Node plugin (no binary build)

OpenDeck plugin protocol matches the Stream Deck SDK: connect to `ws://127.0.0.1:<port>`,
register with `-registerEvent`, handle `keyDown` events. See the PipeWire Audio plugin
for a reference implementation on Linux.

Override paths without reinstalling:

```bash
export LINK_CTL_PY=/path/to/link_ctl.py
export LINK_CTL_PYTHON=/usr/bin/python3
```

## Performance

- First run after plug-in: ~0.5–1 s (USB open + ioctl).
- Subsequent runs: typically &lt;300 ms (no WebSocket, no desktop app).
- PTZ **center** briefly detaches the kernel driver; leave it as a single button,
  not a rapid-fire macro.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No Insta360 /dev/video device found` | Replug camera; check `ls /dev/video*` |
| `libusb` / permission errors | Install udev rule above |
| Privacy fails on OG Link | Expected — use Link 2 / 2 Pro only |
| Button shows text output | Ensure `--quiet` or use provided scripts |
| Yellow ! on every key, no labels | Regenerate with `build_opendeck_profile.py --install` — empty `image` triggers OpenDeck's alert icon |

See also [`docs/LINK2_LINUX.md`](LINK2_LINUX.md) for USB backend details.
