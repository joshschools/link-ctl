#!/usr/bin/env bash
# Install the Insta360 Link 2 OpenDeck plugin and optional pre-built profile.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PLUGIN_SRC="$REPO/streamdeck/opendeck-plugin/com.jschools.insta360link2.sdPlugin"
PLUGIN_DEST="${XDG_CONFIG_HOME:-$HOME/.config}/opendeck/plugins/com.jschools.insta360link2.sdPlugin"
INSTALL_PROFILE=1
NO_RESTART=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Install the link-ctl Insta360 Link 2 OpenDeck plugin.

Options:
  --no-profile   Skip installing the Link2Plugin profile
  --no-restart   Skip restarting OpenDeck after profile install
  -h, --help     Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-profile) INSTALL_PROFILE=0 ;;
    --no-restart) NO_RESTART=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

if [[ ! -d "$PLUGIN_SRC" ]]; then
  echo "Plugin source not found: $PLUGIN_SRC" >&2
  exit 1
fi

mkdir -p "$(dirname "$PLUGIN_DEST")"
rm -rf "$PLUGIN_DEST"
cp -a "$PLUGIN_SRC" "$PLUGIN_DEST"

# Record link-ctl location for the Node plugin runtime.
PYTHON="/usr/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi
cat > "$PLUGIN_DEST/link-ctl-path.json" <<EOF
{
  "repoRoot": "$REPO",
  "linkCtlPath": "$REPO/link_ctl.py",
  "python": "$PYTHON"
}
EOF

echo "Installed plugin → $PLUGIN_DEST"

if command -v npm >/dev/null 2>&1; then
  (cd "$PLUGIN_DEST" && npm install --omit=dev --silent)
  echo "Installed npm dependencies (ws)"
else
  echo "Warning: npm not found — install Node.js 20+ and run: cd \"$PLUGIN_DEST\" && npm install" >&2
fi

if [[ "$INSTALL_PROFILE" == "1" ]]; then
  args=(python3 "$REPO/tools/build_opendeck_plugin_profile.py" --install)
  if [[ "$NO_RESTART" == "1" ]]; then
    args+=(--no-restart)
  fi
  "${args[@]}"
fi

echo "Done. Open OpenDeck → Plugins and confirm \"Insta360 Link 2\" is enabled."
