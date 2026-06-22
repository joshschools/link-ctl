#!/usr/bin/env python3
"""Generate 72x72 and @2x PNG icons for the Insta360 Link 2 OpenDeck plugin."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ICONS = Path(__file__).resolve().parent

# (filename stem, bg on, bg off or None, svg body for ON state)
# OFF state uses same svg with dimmed opacity overlay
TOGGLES = [
    ("track", "#2563eb", "#334155", """
      <circle cx="36" cy="22" r="8" fill="#fff"/>
      <rect x="28" y="30" width="16" height="24" rx="8" fill="#fff"/>
    """),
    ("desk", "#7c3aed", "#4c1d95", """
      <rect x="24" y="22" width="24" height="14" rx="4" fill="#fff"/>
      <line x1="14" y1="40" x2="58" y2="40" stroke="#fff" stroke-width="3"/>
      <line x1="20" y1="40" x2="20" y2="54" stroke="#fff" stroke-width="3"/>
      <line x1="52" y1="40" x2="52" y2="54" stroke="#fff" stroke-width="3"/>
    """),
    ("overhead", "#0369a1", "#0c4a6e", """
      <line x1="36" y1="14" x2="36" y2="34" stroke="#fff" stroke-width="3"/>
      <polyline points="28,22 36,14 44,22" fill="none" stroke="#fff" stroke-width="3"/>
      <rect x="18" y="38" width="36" height="16" rx="4" fill="#fff"/>
    """),
    ("mirror", "#9333ea", "#581c87", """
      <line x1="36" y1="16" x2="36" y2="56" stroke="#fff" stroke-width="3"/>
      <polygon points="18,28 30,28 24,40" fill="#fff"/>
      <polygon points="54,44 42,44 48,32" fill="#fff"/>
    """),
    ("board", "#c026d3", "#86198f", """
      <rect x="14" y="16" width="44" height="34" rx="4" fill="none" stroke="#fff" stroke-width="2"/>
      <line x1="20" y1="54" x2="48" y2="28" stroke="#fff" stroke-width="3"/>
    """),
    ("privacy", "#b91c1c", "#7f1d1d", """
      <rect x="22" y="24" width="28" height="14" rx="10" fill="none" stroke="#fff" stroke-width="2"/>
      <polygon points="36,38 22,54 50,54" fill="#fff"/>
      <line x1="18" y1="18" x2="54" y2="54" stroke="#fff" stroke-width="4"/>
    """),
    ("hdr", "#ca8a04", "#713f12", """
      <text x="36" y="42" text-anchor="middle" font-family="DejaVu Sans, sans-serif"
            font-size="22" font-weight="bold" fill="#fff">HDR</text>
    """),
]

SINGLES = [
    ("center", "#0d9488", """
      <circle cx="36" cy="36" r="16" fill="none" stroke="#fff" stroke-width="3"/>
      <line x1="36" y1="12" x2="36" y2="24" stroke="#fff" stroke-width="3"/>
      <line x1="36" y1="48" x2="36" y2="60" stroke="#fff" stroke-width="3"/>
      <line x1="12" y1="36" x2="24" y2="36" stroke="#fff" stroke-width="3"/>
      <line x1="48" y1="36" x2="60" y2="36" stroke="#fff" stroke-width="3"/>
    """),
    ("reset", "#c2410c", """
      <path d="M 36 18 A 18 18 0 1 1 20 48" fill="none" stroke="#fff" stroke-width="3"/>
      <polygon points="40,14 54,18 46,30" fill="#fff"/>
    """),
    ("zoom-in", "#15803d", """
      <circle cx="32" cy="32" r="14" fill="none" stroke="#fff" stroke-width="3"/>
      <line x1="44" y1="44" x2="56" y2="56" stroke="#fff" stroke-width="3"/>
      <line x1="24" y1="32" x2="40" y2="32" stroke="#fff" stroke-width="3"/>
      <line x1="32" y1="24" x2="32" y2="40" stroke="#fff" stroke-width="3"/>
    """),
    ("zoom-out", "#166534", """
      <circle cx="32" cy="32" r="14" fill="none" stroke="#fff" stroke-width="3"/>
      <line x1="44" y1="44" x2="56" y2="56" stroke="#fff" stroke-width="3"/>
      <line x1="24" y1="32" x2="40" y2="32" stroke="#fff" stroke-width="3"/>
    """),
    ("normal", "#475569", """
      <rect x="20" y="22" width="32" height="24" rx="4" fill="none" stroke="#fff" stroke-width="2"/>
      <circle cx="52" cy="26" r="4" fill="#fff"/>
    """),
    ("plugin", "#0f172a", """
      <circle cx="36" cy="36" r="20" fill="none" stroke="#fff" stroke-width="4"/>
      <circle cx="36" cy="36" r="10" fill="#38bdf8"/>
    """),
]


def svg(bg: str, body: str, size: int = 72) -> str:
    scale = size / 72
    if scale != 1:
        body = f'<g transform="scale({scale})">{body}</g>'
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" rx="12" fill="{bg}"/>
  {body}
</svg>'''


def render(svg_text: str, out: Path, size: int) -> None:
    cmd = ["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(out)]
    subprocess.run(cmd, input=svg_text.encode(), check=True)


def main() -> int:
    for stem, on_bg, off_bg, body in TOGGLES:
        for state, bg in (("on", on_bg), ("off", off_bg)):
            for size in (72, 144):
                suffix = "@2x" if size == 144 else ""
                out = ICONS / f"{stem}-{state}{suffix}.png"
                render(svg(bg, body, 72 if size == 72 else 72), out, size)

    for stem, bg, body in SINGLES:
        for size in (72, 144):
            suffix = "@2x" if size == 144 else ""
            out = ICONS / f"{stem}{suffix}.png"
            render(svg(bg, body, 72), out, size)

    for stem in ("track", "desk", "mirror"):
        (ICONS / f"{stem}.png").write_bytes((ICONS / f"{stem}-on.png").read_bytes())
        (ICONS / f"{stem}@2x.png").write_bytes((ICONS / f"{stem}-on@2x.png").read_bytes())

    count = len(list(ICONS.glob("*.png")))
    print(f"Generated {count} PNG icons in {ICONS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
