#!/usr/bin/env python3
"""Generate an OpenDeck profile using the Insta360 Link 2 native plugin actions.

Compact 15-key MK.2 layout — 11 keys used, overhead removed.

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

# index, bg_off, bg_on, action suffix, icon stem, is_toggle
BUTTONS: list[tuple[int, str, str, str, str, bool]] = [
    (0,  '#475569', '#2563eb', 'track',      'track',    True),
    (1,  '#475569', '#7c3aed', 'deskview',   'desk',     True),
    (2,  '#475569', '#9333ea', 'mirror',     'mirror',   True),
    (3,  '#475569', '#c026d3', 'whiteboard', 'board',    True),
    (4,  '#0d9488', '#0d9488', 'center',     'center',   False),
    (5,  '#475569', '#ca8a04', 'hdr',        'hdr',      True),
    (6,  '#475569', '#b91c1c', 'privacy',    'privacy',  True),
    (7,  '#475569', '#475569', 'normal',     'normal',   False),
    (8,  '#15803d', '#15803d', 'zoomin',     'zoom-in',  False),
    (9,  '#166534', '#166534', 'zoomout',    'zoom-out', False),
    (10, '#c2410c', '#c2410c', 'reset',      'reset',    False),
]

ACTION_NAMES = {
    'track': 'AI Tracking',
    'deskview': 'DeskView',
    'mirror': 'Mirror',
    'whiteboard': 'Whiteboard',
    'privacy': 'Privacy',
    'hdr': 'HDR',
    'center': 'Center',
    'reset': 'Reset Camera',
    'normal': 'Normal Mode',
    'zoomin': 'Zoom In',
    'zoomout': 'Zoom Out',
}


def plugin_icon(stem: str, *, on: bool = True) -> str:
    if stem in ('track', 'desk', 'mirror', 'board', 'privacy', 'hdr'):
        state = 'on' if on else 'off'
        return f'plugins/{PLUGIN_DIR}/icons/{stem}-{state}.png'
    return f'plugins/{PLUGIN_DIR}/icons/{stem}.png'


def _state(label: str, bg: str, icon: str) -> dict:
    return {
        'alignment': 'bottom',
        'background_colour': bg,
        'colour': '#FFFFFF',
        'family': 'Liberation Sans',
        'image': icon,
        'image_scale': 80,
        'name': '',
        'show': True,
        'size': 11,
        'stroke_colour': '#000000',
        'stroke_size': 0,
        'style': 'Regular',
        'text': label,
        'underline': False,
    }


def _make_key(
    index: int,
    bg_off: str,
    bg_on: str,
    suffix: str,
    icon_stem: str,
    is_toggle: bool,
) -> dict:
    uuid = f'com.jschools.insta360link2.{suffix}'
    name = ACTION_NAMES.get(suffix, suffix)
    if is_toggle:
        states = [
            _state('OFF', bg_off, plugin_icon(icon_stem, on=False)),
            _state('ON', bg_on, plugin_icon(icon_stem, on=True)),
        ]
        action_icon = plugin_icon(icon_stem, on=True)
    else:
        labels = {
            'center': 'Center',
            'reset': 'Reset',
            'normal': 'Normal',
            'zoom-in': 'Zoom+',
            'zoom-out': 'Zoom−',
        }
        label = labels.get(icon_stem, name)
        state = _state(label, bg_on, plugin_icon(icon_stem))
        states = [dict(state)]
        action_icon = plugin_icon(icon_stem)
    return {
        'action': {
            'controllers': ['Keypad', 'Encoder'],
            'disable_automatic_states': False,
            'icon': action_icon,
            'name': name,
            'plugin': PLUGIN_DIR,
            'property_inspector': None,
            'supported_in_multi_actions': True,
            'tooltip': name,
            'uuid': uuid,
            'visible_in_action_list': True,
            'states': [dict(s) for s in states],
        },
        'children': None,
        'context': f'Keypad.{index}.0',
        'current_state': 0,
        'settings': {},
        'states': [dict(s) for s in states],
    }


def build_profile() -> dict:
    keys = [
        _make_key(idx, bg_off, bg_on, suffix, icon, toggle)
        for idx, bg_off, bg_on, suffix, icon, toggle in BUTTONS
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
