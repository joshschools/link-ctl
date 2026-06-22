#!/usr/bin/env python3
"""probe_hardware_gaps.py — Gentle Link 2 hardware gap probes on Linux USB.

Probes unmapped XU selectors and func-enable bitmask bits one at a time,
with recover() between risky steps. No libusb reset. ioctl-only unless
--detach is passed (PTZ / deskview-tilt experiments only).

    python3 tools/probe_hardware_gaps.py              # read-only + safe bit flips
    python3 tools/probe_hardware_gaps.py --only smartcomp,head-list
    python3 tools/probe_hardware_gaps.py --deskview-tilt --detach
    python3 tools/probe_hardware_gaps.py --json | jq .

See docs/LINK2_LINUX.md and DEVELOPMENT.md for context.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import link_ctl as lc
import link_usb_linux as ul

# Func-enable bit names (SDK ExtendFunction enum order; bit 0 = AiZoom / smart comp).
BIT_NAMES: dict[int, str] = {
    0: 'smartcomposition',
    1: 'af',
    2: 'hdr',
    3: 'mirror',
    4: 'gesture-zoom',
    5: 'vscreen',
    6: 'enable-startup',
    7: 'single-tap',
    8: 'full-tracking',
    9: 'gesture-track',
    10: 'gesture-whiteboard',
    11: 'privacy',
}

# Bits safe to flip on Link 2 (empirical — bit 5+ can errno 71 / hang firmware).
SAFE_FLIP_BITS = (0, 2, 3, 4)

READ_ONLY_SELECTORS = (
    ('head-list', 9, 0x14, 97, 'face list when tracking (GET_LEN=97 on Link 2)'),
    ('track-target', 9, 0x15, 16, 'track target descriptor (GET_LEN=16)'),
)

AUDIO_CANDIDATES = (
    ('noise-cancel', 9, 0x07, 1),
)


@dataclass
class ProbeResult:
    name: str
    verdict: str
    detail: str = ''
    data: dict = field(default_factory=dict)


def _recover() -> None:
    try:
        ul.recover()
        time.sleep(1.0)
        lc.reset_usb_caches()
    except Exception as e:
        print(f'  recover warning: {e}', file=sys.stderr)


def _bitmask() -> int:
    return int.from_bytes(lc._uvc_get(9, 0x1B, 2), 'little')


def probe_bitmask_bit(bit: int, *, flip: bool) -> ProbeResult:
    name = BIT_NAMES.get(bit, f'bit{bit}')
    try:
        cur = _bitmask()
        cur_on = bool(cur & (1 << bit))
        out = {'cur_mask': f'0x{cur:04x}', 'cur_on': cur_on}
        if not flip:
            return ProbeResult(name, 'READ_ONLY', f'bit {bit} = {cur_on}', out)
        if bit not in SAFE_FLIP_BITS:
            return ProbeResult(name, 'SKIPPED',
                               f'bit {bit} not in safe flip set (can hang firmware)', out)
        test = cur ^ (1 << bit)
        lc._uvc_set(9, 0x1B, test.to_bytes(2, 'little'))
        time.sleep(0.5)
        rb = _bitmask()
        rb_on = bool(rb & (1 << bit))
        persisted = rb_on != cur_on
        out.update({'test_mask': f'0x{test:04x}', 'readback_on': rb_on, 'persisted': persisted})
        lc._uvc_set(9, 0x1B, cur.to_bytes(2, 'little'))
        time.sleep(0.3)
        verdict = 'SUPPORTED' if persisted else 'ACCEPTS_NOOP'
        return ProbeResult(name, verdict, f'bit {bit} flip {"stuck" if persisted else "no-op"}', out)
    except Exception as e:
        _recover()
        return ProbeResult(name, 'ERROR', str(e))


def probe_read_only(name: str, unit: int, sel: int, length: int,
                    note: str = '') -> ProbeResult:
    try:
        try:
            ln = ul.xu_get_len(unit, sel)
            if ln and ln > length:
                length = ln
        except Exception:
            pass
        raw = lc._uvc_get(unit, sel, length)
        nz = sum(1 for b in raw if b)
        return ProbeResult(
            name, 'READ_OK',
            f'{note}; {nz}/{length} nonzero bytes',
            {'hex_head': raw[:32].hex(), 'nonzero': nz, 'len': length})
    except Exception as e:
        return ProbeResult(name, 'UNSUPPORTED', str(e))


def probe_noise_cancel(*, flip: bool) -> ProbeResult:
    try:
        cur = lc._uvc_get(9, 0x07, 1)[0]
        out = {'cur': cur}
        if not flip:
            return ProbeResult('noise-cancel', 'READ_OK', f'value={cur}', out)
        test = 0 if cur else 1
        lc._uvc_set(9, 0x07, bytes([test]))
        time.sleep(0.4)
        rb = lc._uvc_get(9, 0x07, 1)[0]
        lc._uvc_set(9, 0x07, bytes([cur]))
        out['readback'] = rb
        verdict = 'SUPPORTED' if rb == test else 'ACCEPTS_NOOP'
        return ProbeResult('noise-cancel', verdict, f'wrote {test} read {rb}', out)
    except Exception as e:
        return ProbeResult('noise-cancel', 'ERROR', str(e))


def probe_unit11_scan() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    try:
        h = ul._get_handle()
        for sel in range(0x01, 0x20):
            try:
                ln = h.xu_get_len(11, sel)
            except Exception:
                continue
            if not ln or ln > 256:
                continue
            try:
                raw = h.get(11, sel, min(ln, 64))
            except Exception:
                continue
            if any(raw):
                results.append(ProbeResult(
                    f'unit11-0x{sel:02x}', 'READ_OK',
                    f'len={ln}',
                    {'hex': raw.hex()}))
    except Exception as e:
        results.append(ProbeResult('unit11-scan', 'ERROR', str(e)))
    return results


def probe_deskview_tilt(*, detach: bool) -> ProbeResult:
    """Measure pan/tilt before/after deskview; optional manual tilt with detach."""
    if detach:
        os.environ['LINK_CTL_USB_DETACH'] = '1'
        os.environ.pop('LINK_CTL_NO_DETACH', None)
    else:
        os.environ['LINK_CTL_NO_DETACH'] = '1'

    dev = ul._find_video_device()
    try:
        with ul.video_stream(seconds=22.0, device=dev) as streaming:
            p0, t0 = lc.read_pantilt()
            mode_id, flag = lc.AI_MODE_BYTES['deskview']
            got = lc._link2_drive_ai_mode_streaming('deskview', mode_id, flag, streaming)
            time.sleep(2.0)
            p1, t1 = lc.read_pantilt()
            out = {
                'streaming': streaming,
                'before': {'pan': p0, 'tilt': t0},
                'after_deskview': {'pan': p1, 'tilt': t1, 'byte0': got,
                                   'mode': lc.read_ai_mode()},
                'gimbal_moved': (p1 != p0 or t1 != t0),
            }
            if detach and streaming:
                lc.write_pantilt(0, -120000)
                time.sleep(1.5)
                p2, t2 = lc.read_pantilt()
                out['after_manual_tilt'] = {'pan': p2, 'tilt': t2}
                lc.write_pantilt(0, 0)
        lc.write_ai_mode('normal')
        time.sleep(1.0)
        detail = (
            f"deskview byte0={out['after_deskview'].get('byte0')} "
            f"tilt {t0}→{t1} (gimbal_moved={out['gimbal_moved']})"
        )
        verdict = 'NO_GIMBAL_TILT' if not out['gimbal_moved'] else 'GIMBAL_MOVED'
        return ProbeResult('deskview-tilt', verdict, detail, out)
    except Exception as e:
        return ProbeResult('deskview-tilt', 'ERROR', str(e))
    finally:
        _recover()


def run_probes(*, only: set[str] | None, flip: bool, deskview_tilt: bool,
               detach: bool, verbose: bool) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    _recover()

    def want(name: str) -> bool:
        return only is None or name in only or any(name.startswith(p) for p in only)

    if want('smartcomposition') or want('bitmask'):
        for bit in sorted(BIT_NAMES):
            key = BIT_NAMES[bit]
            if only and key not in only and 'bitmask' not in only:
                continue
            r = probe_bitmask_bit(bit, flip=flip)
            results.append(r)
            if verbose:
                print(f'  [{r.verdict}] {r.name}: {r.detail}', file=sys.stderr)
            _recover()

    for name, unit, sel, ln, note in READ_ONLY_SELECTORS:
        if not want(name):
            continue
        if name == 'head-list-track' or (only and 'head-list' in only):
            pass
        r = probe_read_only(name, unit, sel, ln, note)
        results.append(r)
        if verbose:
            print(f'  [{r.verdict}] {r.name}: {r.detail}', file=sys.stderr)

    if want('head-list') and flip:
        try:
            lc.write_ai_mode('track')
            time.sleep(3.0)
            r = probe_read_only('head-list-tracking', 9, 0x14, 97,
                                'with track on')
            results.append(r)
            r2 = probe_read_only('track-target-tracking', 9, 0x15, 16,
                                 'with track on')
            results.append(r2)
            lc.write_ai_mode('normal')
            _recover()
        except Exception as e:
            results.append(ProbeResult('head-list-tracking', 'ERROR', str(e)))
            _recover()

    if want('noise-cancel'):
        results.append(probe_noise_cancel(flip=flip))
        _recover()

    if want('unit11') or want('audio'):
        results.extend(probe_unit11_scan())
        _recover()

    if deskview_tilt or want('deskview-tilt'):
        results.append(probe_deskview_tilt(detach=detach))
        _recover()

    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', metavar='NAMES',
                    help='comma-separated probe names (smartcomposition, head-list, …)')
    ap.add_argument('--flip', action='store_true',
                    help='flip writable bits (default: read bitmask + read-only GETs)')
    ap.add_argument('--deskview-tilt', action='store_true',
                    help='run deskview pan/tilt experiment (needs stream)')
    ap.add_argument('--detach', action='store_true',
                    help='allow libusb detach for manual tilt after deskview')
    ap.add_argument('--json', action='store_true', help='JSON to stdout')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--list', action='store_true', help='list probe names and exit')
    args = ap.parse_args()

    if args.list:
        print('bitmask bits:', ', '.join(BIT_NAMES.values()))
        print('selectors:', ', '.join(n for n, *_ in READ_ONLY_SELECTORS))
        print('extras: noise-cancel, unit11, deskview-tilt')
        return 0

    only = {n.strip() for n in args.only.split(',')} if args.only else None
    flip = args.flip or (only and any(
        x in only for x in ('smartcomposition', 'noise-cancel', 'bitmask')))

    results = run_probes(only=only, flip=flip or args.flip,
                         deskview_tilt=args.deskview_tilt,
                         detach=args.detach, verbose=args.verbose)

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print('\n── Hardware gap probe summary ──')
        for r in results:
            print(f'  {r.name:<22} {r.verdict:<16} {r.detail}')
        supported = [r.name for r in results if r.verdict == 'SUPPORTED']
        if supported:
            print(f'\nConfirmed writable: {", ".join(supported)}')

    _recover()
    return 0


if __name__ == '__main__':
    sys.exit(main())
