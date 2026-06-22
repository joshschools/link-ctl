#!/usr/bin/env python3
"""Generate an OpenDeck profile using the Insta360 Link 2 native plugin actions.

Usage:
    python3 tools/build_opendeck_plugin_profile.py
    python3 tools/build_opendeck_plugin_profile.py --install
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PLUGIN_DIR = 'com.jschools.insta360link2.sdPlugin'
PROFILE_NAME = 'Link2Plugin'

TRANSPARENT_IMAGE = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIW2NgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg=='
)

# index, label, bg, action suffix, icon stem
BUTTONS: list[tuple[int, str, str, str, str]] = [
    (0,  'Track',    '#2563eb', 'trackon',      'track'),
    (1,  'Track\nOff', '#1e40af', 'trackoff',     'track'),
    (2,  'Desk',     '#7c3aed', 'deskviewon',   'desk'),
    (3,  'Desk\nOff', '#5b21b6', 'deskviewoff',  'desk'),
    (4,  'Center',   '#0d9488', 'center',       'center'),
    (5,  'Overhead', '#0369a1', 'overheadon',   'desk'),
    (6,  'Over\nOff', '#075985', 'overheadoff',  'desk'),
    (7,  'Board',    '#c026d3', 'whiteboardon', 'desk'),
    (8,  'Board\nOff', '#a21caf', 'whiteboardoff', 'desk'),
    (9,  'Mirror',   '#9333ea', 'mirroron',     'mirror'),
    (10, 'Zoom +',   '#15803d', 'zoomin',       'center'),
    (11, 'Zoom −',   '#166534', 'zoomout',      'center'),
    (12, 'Reset',    '#c2410c', 'reset',        'reset'),
    (13, 'Privacy',  '#b91c1c', 'privacyon',    'reset'),
    (14, 'Priv\nOff', '#991b1b', 'privacyoff',   'reset'),
]

ACTION_NAMES = {
    'trackon': 'Track On',
    'trackoff': 'Track Off',
    'deskviewon': 'DeskView On',
    'deskviewoff': 'DeskView Off',
    'mirroron': 'Mirror On',
    'center': 'Center',
    'reset': 'Reset Camera',
    'zoomin': 'Zoom In',
    'zoomout': 'Zoom Out',
    'overheadon': 'Overhead On',
    'overheadoff': 'Overhead Off',
    'whiteboardon': 'Whiteboard On',
    'whiteboardoff': 'Whiteboard Off',
    'privacyon': 'Privacy On',
    'privacyoff': 'Privacy Off',
}


def plugin_icon(stem: str) -> str:
    return f'plugins/{PLUGIN_DIR}/icons/{stem}.png'


def _state(label: str, bg: str, icon: str) -> dict:
    return {
        'alignment': 'middle',
        'background_colour': bg,
        'colour': '#FFFFFF',
        'family': 'Liberation Sans',
        'image': TRANSPARENT_IMAGE,
        'image_scale': 10,
        'name': '',
        'show': True,
        'size': 13,
        'stroke_colour': '#000000',
        'stroke_size': 2,
        'style': 'Regular',
        'text': label,
        'underline': False,
    }


def _make_key(index: int, label: str, bg: str, suffix: str, icon_stem: str) -> dict:
    uuid = f'com.jschools.insta360link2.{suffix}'
    icon = plugin_icon(icon_stem)
    state = _state(label, bg, icon)
    return {
        'action': {
            'controllers': ['Keypad', 'Encoder'],
            'disable_automatic_states': False,
            'icon': icon,
            'name': ACTION_NAMES.get(suffix, suffix),
            'plugin': PLUGIN_DIR,
            'property_inspector': None,
            'supported_in_multi_actions': True,
            'tooltip': ACTION_NAMES.get(suffix, suffix),
            'uuid': uuid,
            'visible_in_action_list': True,
            'states': [dict(state)],
        },
        'children': None,
        'context': f'Keypad.{index}.0',
        'current_state': 0,
        'settings': {},
        'states': [dict(state)],
    }


def build_profile() -> dict:
    keys = [
        _make_key(idx, label, bg, suffix, icon)
        for idx, label, bg, suffix, icon in BUTTONS
    ]
    return {'keys': keys, 'sliders': []}


def opendeck_config_dir() -> Path:
    return Path.home() / '.config' / 'opendeck'


def set_selected_profile(config_dir: Path, device_id: str, profile_name: str) -> None:
    cfg_path = config_dir / 'profiles' / f'{device_id}.json'
    cfg: dict = {'selected_profile': profile_name}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
        except json.JSONDecodeError:
            pass
    cfg['selected_profile'] = profile_name
    cfg_path.write_text(json.dumps(cfg, indent=2) + '\n')
    print(f'Selected profile "{profile_name}" for {device_id}')


def install_profile(profile_path: Path, config_dir: Path) -> list[Path]:
    installed: list[Path] = []
    profiles_root = config_dir / 'profiles'
    if not profiles_root.is_dir():
        raise SystemExit(f'OpenDeck profiles dir not found: {profiles_root}')
    for device_dir in sorted(profiles_root.glob('sd-*')):
        if not device_dir.is_dir():
            continue
        dest = device_dir / profile_path.name
        shutil.copy2(profile_path, dest)
        installed.append(dest)
        set_selected_profile(config_dir, device_dir.name, PROFILE_NAME)
    return installed


def restart_opendeck() -> None:
    subprocess.run(['killall', 'opendeck'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    subprocess.Popen(
        ['opendeck', '--hide'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print('Restarted OpenDeck.')


def main() -> int:
    ap = argparse.ArgumentParser(description='Build OpenDeck Link2 plugin profile JSON')
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument('--output', type=Path, default=None)
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--no-restart', action='store_true')
    args = ap.parse_args()

    repo = args.repo.resolve()
    output = args.output or (
        repo / 'streamdeck' / 'opendeck-plugin' / f'{PROFILE_NAME}.json'
    )
    profile = build_profile()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2) + '\n')
    print(f'Wrote {output}')

    if not args.install:
        return 0

    paths = install_profile(output, opendeck_config_dir())
    if not paths:
        print('No sd-* device folders — plug in Stream Deck and open OpenDeck once.',
              file=sys.stderr)
        return 1
    for path in paths:
        print(f'Installed → {path}')
    if not args.no_restart:
        restart_opendeck()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
