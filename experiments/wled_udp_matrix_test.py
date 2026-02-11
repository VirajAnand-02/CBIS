#!/usr/bin/env python3
"""Minimal WLED UDP matrix test (DRGB/DNRGB).

- Sends simple test patterns to a WLED device using UDP realtime.
- Supports arbitrary matrix sizes. If LED count > 490 (or packet would exceed MTU),
  it automatically uses DNRGB (protocol 4) and chunks packets.

No third-party dependencies.

Examples:
  python wled_udp_matrix_test.py --wled 192.168.0.112 --width 16 --height 16 --serpentine --pattern rainbow
  python wled_udp_matrix_test.py --wled 192.168.0.112 --width 30 --height 30 --serpentine --pattern wipe
"""

from __future__ import annotations

import argparse
import colorsys
import socket
import time
from typing import Iterable, List, Tuple

WLED_DEFAULT_PORT = 21324

# WLED realtime protocol IDs
PROTO_DRGB = 2
PROTO_DNRGB = 4

# Per WLED docs
DRGB_MAX_LEDS = 490
DNRGB_MAX_LEDS_PER_PACKET = 489

# Safe-ish UDP payload target (fits typical MTU 1500 with IP/UDP headers)
SAFE_UDP_BYTES = 1472


def xy_to_index(x: int, y: int, w: int, serpentine: bool) -> int:
    if not serpentine:
        return y * w + x
    return y * w + (x if (y % 2 == 0) else (w - 1 - x))


def pack_drgb(timeout_s: int, rgb_bytes: bytes) -> bytes:
    return bytes([PROTO_DRGB, timeout_s & 0xFF]) + rgb_bytes


def pack_dnrgb(timeout_s: int, start_index: int, rgb_bytes: bytes) -> bytes:
    hi = (start_index >> 8) & 0xFF
    lo = start_index & 0xFF
    return bytes([PROTO_DNRGB, timeout_s & 0xFF, hi, lo]) + rgb_bytes


def iter_packets(timeout_s: int, led_rgb: bytes) -> Iterable[bytes]:
    """Yield one or more UDP packets, DRGB or chunked DNRGB."""
    led_count = len(led_rgb) // 3

    # DRGB only works up to 490 LEDs, and packet must fit.
    drgb_len = 2 + len(led_rgb)
    if led_count <= DRGB_MAX_LEDS and drgb_len <= SAFE_UDP_BYTES:
        yield pack_drgb(timeout_s, led_rgb)
        return

    # Otherwise use DNRGB and chunk.
    start = 0
    while start < led_count:
        chunk_leds = min(DNRGB_MAX_LEDS_PER_PACKET, led_count - start)
        chunk = led_rgb[start * 3 : (start + chunk_leds) * 3]
        yield pack_dnrgb(timeout_s, start, chunk)
        start += chunk_leds


def make_frame(cfg, t: float) -> bytes:
    """Return RGB bytes in WLED LED order (index 0..N-1)."""
    w, h = cfg.width, cfg.height
    n = w * h

    # Build per-pixel colors then map to LED index.
    rgb = bytearray(n * 3)

    def set_led(idx: int, r: int, g: int, b: int) -> None:
        base = idx * 3
        rgb[base : base + 3] = bytes((r & 0xFF, g & 0xFF, b & 0xFF))

    # Patterns
    if cfg.pattern == "solid":
        r, g, b = cfg.color
        for i in range(n):
            set_led(i, r, g, b)

    elif cfg.pattern == "wipe":
        # Moving vertical bar
        x0 = int((t * cfg.speed) % w)
        for y in range(h):
            for x in range(w):
                on = (x == x0)
                r, g, b = (cfg.color if on else (0, 0, 0))
                tx = (w - 1 - x) if cfg.flipx else x
                ty = (h - 1 - y) if cfg.flipy else y
                idx = xy_to_index(tx, ty, w, cfg.serpentine)
                set_led(idx, r, g, b)

    elif cfg.pattern == "checker":
        for y in range(h):
            for x in range(w):
                on = ((x + y) % 2 == 0)
                r, g, b = (cfg.color if on else (0, 0, 0))
                tx = (w - 1 - x) if cfg.flipx else x
                ty = (h - 1 - y) if cfg.flipy else y
                idx = xy_to_index(tx, ty, w, cfg.serpentine)
                set_led(idx, r, g, b)

    elif cfg.pattern == "rainbow":
        # Hue varies across X, animated over time
        for y in range(h):
            for x in range(w):
                hue = ((x / max(1, w - 1)) + t * cfg.speed) % 1.0
                rr, gg, bb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                r, g, b = int(rr * 255), int(gg * 255), int(bb * 255)
                tx = (w - 1 - x) if cfg.flipx else x
                ty = (h - 1 - y) if cfg.flipy else y
                idx = xy_to_index(tx, ty, w, cfg.serpentine)
                set_led(idx, r, g, b)

    else:
        raise ValueError(f"Unknown pattern: {cfg.pattern}")

    return bytes(rgb)


def parse_color(s: str) -> Tuple[int, int, int]:
    parts = s.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Color must be r,g,b")
    try:
        r, g, b = (int(p.strip()) for p in parts)
    except ValueError as e:
        raise argparse.ArgumentTypeError("Color must be r,g,b integers") from e
    for v in (r, g, b):
        if v < 0 or v > 255:
            raise argparse.ArgumentTypeError("Color channels must be 0..255")
    return r, g, b


def parse_args():
    p = argparse.ArgumentParser(description="Minimal WLED UDP matrix test (DRGB/DNRGB)")
    p.add_argument("--wled", required=True, help="WLED host/IP")
    p.add_argument("--port", type=int, default=WLED_DEFAULT_PORT, help="WLED UDP realtime port")
    p.add_argument("--width", type=int, default=16)
    p.add_argument("--height", type=int, default=16)
    p.add_argument("--serpentine", action="store_true")
    p.add_argument("--flipx", action="store_true", help="Flip X mapping")
    p.add_argument("--flipy", action="store_true", help="Flip Y mapping")

    p.add_argument("--pattern", choices=["solid", "wipe", "checker", "rainbow"], default="rainbow")
    p.add_argument("--color", type=parse_color, default=(255, 0, 0), help="Used by solid/wipe/checker")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--speed", type=float, default=1.0, help="Animation speed")
    p.add_argument("--duration", type=float, default=0.0, help="Seconds to run (0 = until Ctrl+C)")
    p.add_argument("--timeout", type=int, default=2, help="WLED realtime timeout seconds (byte 1)")
    p.add_argument("--no-blackout", action="store_true", help="Do not send blackout on exit")
    return p.parse_args()


def main() -> int:
    cfg = parse_args()

    host = cfg.wled.replace("http://", "").replace("https://", "").rstrip("/")
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        print(f"Error: could not resolve host '{cfg.wled}'")
        return 2

    n = cfg.width * cfg.height
    # Print what protocol will be used.
    planned_len = 2 + n * 3
    proto = "DRGB" if (n <= DRGB_MAX_LEDS and planned_len <= SAFE_UDP_BYTES) else "DNRGB (chunked)"
    print(f"Target {ip}:{cfg.port} leds={n} ({cfg.width}x{cfg.height}) proto={proto}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    frame_interval = 1.0 / cfg.fps if cfg.fps > 0 else 0.0
    start = time.monotonic()
    next_frame = start

    try:
        while True:
            now = time.monotonic()
            if frame_interval and now < next_frame:
                time.sleep(min(0.01, next_frame - now))
                continue
            if frame_interval:
                next_frame += frame_interval

            t = now - start
            if cfg.duration and t >= cfg.duration:
                break

            led_rgb = make_frame(cfg, t)
            for pkt in iter_packets(cfg.timeout, led_rgb):
                sock.sendto(pkt, (ip, cfg.port))

    except KeyboardInterrupt:
        pass
    finally:
        if not cfg.no_blackout:
            blackout = bytes([0]) * (n * 3)
            # use the same protocol selection for blackout
            for pkt in iter_packets(cfg.timeout, blackout):
                sock.sendto(pkt, (ip, cfg.port))
        sock.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
