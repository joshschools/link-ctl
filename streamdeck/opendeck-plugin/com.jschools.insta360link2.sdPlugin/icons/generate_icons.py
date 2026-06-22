#!/usr/bin/env python3
"""Generate 72x72 and @2x PNG icons for the Insta360 Link 2 OpenDeck plugin.

Icons are derived from Lucide (MIT): https://github.com/lucide-icons/lucide
Vendored SVGs live in icons/lucide/.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ICONS = Path(__file__).resolve().parent
LUCIDE = ICONS / "lucide"

OFF_BG = "#475569"  # slate-600 — muted gray for OFF toggles

# (stem, lucide file, ON background)
TOGGLES: list[tuple[str, str, str]] = [
    ("track", "user-round", "#2563eb"),
    ("desk", "lamp-desk", "#7c3aed"),
    ("mirror", "flip-horizontal", "#9333ea"),
    ("board", "presentation", "#c026d3"),
    ("privacy", "eye-off", "#b91c1c"),
    ("hdr", "sun", "#ca8a04"),
]

# (stem, lucide file, background, label below icon)
SINGLES: list[tuple[str, str, str, str]] = [
    ("center", "crosshair", "#0d9488", "Center"),
    ("reset", "rotate-ccw", "#c2410c", "Reset"),
    ("zoom-in", "zoom-in", "#15803d", "Zoom+"),
    ("zoom-out", "zoom-out", "#166534", "Zoom−"),
    ("normal", "video", "#475569", "Normal"),
    ("plugin", "camera", "#0f172a", ""),
]


def lucide_inner(name: str) -> str:
    svg = (LUCIDE / f"{name}.svg").read_text()
    m = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.DOTALL)
    if not m:
        raise ValueError(f"Could not parse Lucide SVG: {name}")
    inner = m.group(1).strip()
    inner = inner.replace('stroke="currentColor"', 'stroke="#ffffff"')
    inner = inner.replace("stroke='currentColor'", "stroke='#ffffff'")
    return inner


def icon_group(lucide_file: str, *, cx: float = 36, cy: float = 28, scale: float = 1.35) -> str:
    inner = lucide_inner(lucide_file)
    s = scale
    tx = cx - 12 * s
    ty = cy - 12 * s
    return f'<g transform="translate({tx:.2f},{ty:.2f}) scale({s})">{inner}</g>'


def label_text(text: str, *, y: float = 62, size: int = 11) -> str:
    if not text:
        return ""
    return (
        f'<text x="36" y="{y}" text-anchor="middle" '
        f'font-family="DejaVu Sans, Liberation Sans, sans-serif" '
        f'font-size="{size}" font-weight="bold" fill="#ffffff">{text}</text>'
    )


def compose(bg: str, body: str, size: int = 72) -> str:
    scale = size / 72
    if scale != 1:
        body = f'<g transform="scale({scale})">{body}</g>'
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" rx="12" fill="{bg}"/>
  {body}
</svg>'''


def render(svg_text: str, out: Path, size: int) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(out)],
        input=svg_text.encode(),
        check=True,
    )


def generate_toggle(stem: str, lucide_file: str, on_bg: str) -> None:
    icon = icon_group(lucide_file)
    for state, bg, label in (("off", OFF_BG, "OFF"), ("on", on_bg, "ON")):
        body = icon + label_text(label)
        for size in (72, 144):
            suffix = "@2x" if size == 144 else ""
            render(compose(bg, body), ICONS / f"{stem}-{state}{suffix}.png", size)


def generate_single(stem: str, lucide_file: str, bg: str, label: str) -> None:
    body = icon_group(lucide_file) + label_text(label)
    for size in (72, 144):
        suffix = "@2x" if size == 144 else ""
        render(compose(bg, body), ICONS / f"{stem}{suffix}.png", size)


def cleanup_stale() -> None:
    for pattern in ("overhead-*.png", "track.png", "track@2x.png", "desk.png", "desk@2x.png", "mirror.png", "mirror@2x.png"):
        for path in ICONS.glob(pattern):
            path.unlink()


def main() -> int:
    if not LUCIDE.is_dir():
        print(f"Missing Lucide SVG directory: {LUCIDE}", file=sys.stderr)
        return 1

    cleanup_stale()

    for stem, lucide_file, on_bg in TOGGLES:
        generate_toggle(stem, lucide_file, on_bg)

    for stem, lucide_file, bg, label in SINGLES:
        generate_single(stem, lucide_file, bg, label)

    count = len(list(ICONS.glob("*.png")))
    print(f"Generated {count} PNG icons in {ICONS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
