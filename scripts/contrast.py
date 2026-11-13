#!/usr/bin/env python3
"""WCAG contrast of every pair of brand colours.

Usage:
    python contrast.py "#0B0B0C" "#FFD60A" "#FFFFFF"

Pairs under 3:1 are forbidden for any text or graphic edge; 3:1 to 4.5:1 is
large type only (headlines, hooks). Paste the result into brand/BRAND.md.
"""
import itertools, sys


def luminance(hex_colour):
    h = hex_colour.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


if __name__ == "__main__":
    assert round(ratio("#000000", "#FFFFFF"), 1) == 21.0 and round(ratio("#777777", "#777777"), 1) == 1.0
    colours = sys.argv[1:]
    if len(colours) < 2:
        print(__doc__)
        sys.exit(1)
    for a, b in itertools.combinations(colours, 2):
        r = ratio(a, b)
        verdict = "FORBIDDEN" if r < 3 else "large type only" if r < 4.5 else "ok"
        print(f"{a} / {b}: {r:5.2f}:1  {verdict}")
