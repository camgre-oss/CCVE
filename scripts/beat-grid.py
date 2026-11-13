#!/usr/bin/env python3
"""Tempo and beat frames of a music bed, in composition frames.

Usage:
    python beat-grid.py "public/music pack/track.mp3" [--start S] [--frames N]
    python beat-grid.py selftest

--start is the bed's trimBefore in seconds (START_S); --frames is the
composition length. Prints the BPM and every beat as a composition frame, with
the bar position (1-4). The bar count assumes the first detected beat is a
downbeat: check it against the track by ear before snapping drops to it.
Requires ffmpeg on PATH and numpy.
"""
import subprocess, sys
import numpy as np

SR, HOP, FPS = 22050, 512, 30


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def onset_envelope(audio):
    """Positive spectral flux: how much new energy arrives in each hop."""
    n = 2048
    frames = np.lib.stride_tricks.sliding_window_view(audio, n)[::HOP] * np.hanning(n)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(axis=1)
    return np.concatenate([[0], flux - flux.mean()])


def tempo_and_phase(env):
    rate = SR / HOP
    lags = np.arange(int(rate * 60 / 180), int(rate * 60 / 70) + 1)
    ac = np.array([np.dot(env[:-l], env[l:]) for l in lags])
    # Prefer tempos near 120 so a half- or double-time peak does not win by a hair.
    weight = np.exp(-0.5 * (np.log2(60 * rate / lags / 120) / 0.9) ** 2)
    coarse = lags[np.argmax(ac * weight)]
    # Integer lags are ~1% coarse, which drifts several frames over a reel. Refine period and
    # phase together: the comb that lands on the most onset energy across the whole track wins.
    hops = np.arange(len(env))
    best = (-np.inf, coarse, 0.0)
    for period in np.linspace(coarse - 1, coarse + 1, 201):
        for phase in np.arange(0, period, 0.25):
            score = np.interp(np.arange(phase, len(env) - 1, period), hops, env).sum()
            if score > best[0]:
                best = (score, period, phase)
    _, period, phase = best
    # Envelope index i describes the window centred half a window (1024 samples) after i * HOP.
    return 60 * rate / period, (phase * HOP + 1024) / SR


def grid(path, start=0.0, frames=None):
    audio = decode(path)
    bpm, first = tempo_and_phase(onset_envelope(audio))
    beat = 60 / bpm
    total = frames / FPS if frames else len(audio) / SR - start
    k = int(np.ceil((start - first) / beat))           # first beat at or after the trim point
    out = []
    while True:
        t = first + k * beat - start
        if t >= total:
            break
        out.append((round(t * FPS), k % 4 + 1))
        k += 1
    return bpm, out


def selftest():
    bpm, offset, dur = 128, 0.3, 20
    audio = np.zeros(int(SR * dur), np.float32)
    click = np.sin(2 * np.pi * 1000 * np.arange(400) / SR) * np.exp(-np.arange(400) / 80)
    for t in np.arange(offset, dur - 0.1, 60 / bpm):
        audio[int(t * SR):int(t * SR) + 400] += click
    got_bpm, got_first = tempo_and_phase(onset_envelope(audio))
    assert abs(got_bpm - bpm) < 0.15, got_bpm
    assert abs((got_first - offset) % (60 / bpm)) < 1.5 / FPS or abs((got_first - offset) % (60 / bpm) - 60 / bpm) < 1.5 / FPS, got_first
    print(f"selftest ok ({got_bpm:.2f} BPM, first beat {got_first:.3f}s)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["selftest"]:
        selftest()
    elif args:
        start = float(args[args.index("--start") + 1]) if "--start" in args else 0.0
        frames = int(args[args.index("--frames") + 1]) if "--frames" in args else None
        bpm, beats = grid(args[0], start, frames)
        print(f"{bpm:.2f} BPM, beat = {60 / bpm * FPS:.2f} frames")
        print(" ".join(f"f{f}{'|' if bar == 1 else ''}" for f, bar in beats))
        print("('|' marks an assumed downbeat)")
    else:
        print(__doc__)
