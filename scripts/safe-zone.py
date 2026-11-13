#!/usr/bin/env python3
"""Flag graphics that sit where Instagram's UI covers the reel.

Usage:
    python safe-zone.py source.mp4 checkDir [--offset F] [--ads]

checkDir holds a range render (element-<frame>.jpeg). Each frame is diffed
against the source take at frame + offset, so whatever differs is a graphic or
caption. Any graphic pixels inside a forbidden margin are reported with their
bounding box. --ads uses Meta's stricter ad margins (top 270, bottom 670).
Moving entrances and exits may cross a margin; only a resting graphic counts.
Requires ffmpeg on PATH and numpy.
"""
import os, re, subprocess, sys
import numpy as np

W, H = 1080, 1920
DIFF_THRESHOLD = 48        # 8-bit luma difference that counts as "not the source video"
NOISE_PIXELS = 300         # fewer changed pixels than this in a margin is encoder noise


def margins(ads):
    top, bottom = (270, 670) if ads else (150, 340)
    return {"top": (0, 0, W, top), "bottom": (0, H - bottom, W, H),
            "left": (0, 0, 108, H), "right": (W - 108, 0, W, H)}


def gray(path, frame=None):
    cmd = ["ffmpeg", "-v", "error", "-i", path]
    if frame is not None:
        cmd += ["-vf", f"select=eq(n\\,{frame}),scale={W}:{H}", "-frames:v", "1"]
    else:
        cmd += ["-vf", f"scale={W}:{H}"]
    raw = subprocess.run(cmd + ["-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W).astype(np.int16)


def check(mask, bands):
    hits = []
    if mask.mean() > 0.85:
        return ["full-frame graphic: check margins by eye on a guides sheet"]
    for name, (x0, y0, x1, y1) in bands.items():
        sub = mask[y0:y1, x0:x1]
        if sub.sum() >= NOISE_PIXELS:
            ys, xs = np.nonzero(sub)
            hits.append(f"{name}: {int(sub.sum())} px, box x{x0 + xs.min()}-{x0 + xs.max()} y{y0 + ys.min()}-{y0 + ys.max()}")
    return hits


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    source, folder = args[0], args[1]
    offset = int(args[args.index("--offset") + 1]) if "--offset" in args else 0
    bands = margins("--ads" in args)
    frames = sorted((int(m.group(1)), f) for f in os.listdir(folder)
                    if (m := re.match(r"element-(\d+)\.(jpe?g|png)$", f)))
    bad = 0
    for n, f in frames:
        mask = np.abs(gray(os.path.join(folder, f)) - gray(source, n + offset)) > DIFF_THRESHOLD
        for hit in check(mask, bands):
            bad += 1
            print(f"OUT OF ZONE f{n}: {hit}")
    print(f"{len(frames)} frames checked, {bad} hits" if bad else f"{len(frames)} frames checked, safe zone ok")


def selftest():
    bands = margins(False)
    mask = np.zeros((H, W), bool)
    mask[900:1000, 300:700] = True                     # caption in the middle
    assert check(mask, bands) == []
    mask[1700:1760, 300:700] = True                    # caption under the IG description
    hits = check(mask, bands)
    assert len(hits) == 1 and hits[0].startswith("bottom") and "y1700-1759" in hits[0], hits
    print("selftest ok")


if __name__ == "__main__":
    selftest() if sys.argv[1:2] == ["selftest"] else main()
