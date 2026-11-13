#!/usr/bin/env python3
"""Bring a finished reel to delivery loudness without touching the picture.

Usage:
    python loudness.py out/name.mp4 [--target -10]

Writes out/name-loud.mp4 (video stream copied). loudnorm alone stalls around
-15 LUFS on speech: its true-peak ceiling caps the gain. So this compresses,
applies a plain gain into a limiter and re-measures, correcting the gain until the
integrated loudness is within 0.5 LU of the target (the limiter eats some of it).
Requires ffmpeg on PATH. No third-party Python packages.
"""
import os, re, subprocess, sys

LIMIT = 0.75  # -2.5 dBFS sample peak; AAC adds about 1 dB of inter-sample overshoot
COMPRESS = "acompressor=threshold=0.1:ratio=4:attack=5:release=80"  # tames speech peaks so the limiter works less


def measure(path):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = log[log.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1)), \
        float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    src = args[0]
    target = float(args[args.index("--target") + 1]) if "--target" in args else -10.0
    out = os.path.splitext(src)[0] + "-loud.mp4"
    loudness, _ = measure(src)
    gain = target - loudness
    for _ in range(5):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-c:v", "copy",
                        "-af", f"{COMPRESS},volume={gain:.2f}dB,alimiter=limit={LIMIT}:attack=2:release=50:level=false",
                        "-ar", "48000", "-c:a", "aac", "-b:a", "192k", out], check=True)
        loudness, peak = measure(out)
        if abs(loudness - target) < 0.5:
            break
        gain += target - loudness
    note = "" if abs(loudness - target) < 0.5 else "  (limiter saturated: this is the loudest clean level)"
    if peak > -1:
        note += "  WARNING: true peak above -1 dBFS"
    print(f"{loudness:.1f} LUFS, true peak {peak:.1f} dBFS, gain {gain:+.1f} dB -> {out}{note}")


if __name__ == "__main__":
    main()
