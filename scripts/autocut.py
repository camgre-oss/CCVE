#!/usr/bin/env python3
"""Rough cut of a talking-head take: silences, fillers and retakes.

Usage:
    python autocut.py propose take.mp4 take.words.json [--silence-db -35] [--min-silence 0.35] [--pad 0.08]
    python autocut.py apply   take.mp4 [take.cuts.json]
    python autocut.py selftest

propose writes take.cuts.json and prints the list in frames. Nothing is cut yet:
the creator reviews it and flips "apply" per row. apply renders take.cut.mp4
(H.264, 30 fps). Transcribe the cut file once: it is the new master, and whisper
times it better than the long take, whose pauses it smears words into.
Requires ffmpeg on PATH. No third-party Python packages.
"""
import json, os, re, subprocess, sys, tempfile, unicodedata

FPS = 30
# Whisper usually drops disfluencies; these are the ones it does write.
FILLERS = {"eh", "ehh", "ehm", "em", "emm", "mm", "mmm", "hmm", "ah", "uh", "um", "umm", "uhm"}
RETAKE_MIN_WORDS = 3
RETAKE_WINDOW_S = 20


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", text)


def spoken(words):
    return [w for w in words if normalize(w["text"])]


def detect_silences(path, noise_db, min_dur):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn",
                          "-af", f"silencedetect=n={noise_db}dB:d={min_dur}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    duration = probe_duration(path)
    if len(ends) < len(starts):  # take ends in silence
        ends.append(duration)
    return [(max(0.0, s), e) for s, e in zip(starts, ends)], duration


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip())


def find_retakes(words):
    """A run of >= RETAKE_MIN_WORDS words said again shortly after means the first try was abandoned.
    Cut from the first try's start to the second try's start."""
    cuts, norm, i = [], [normalize(w["text"]) for w in words], 0
    while i < len(words):
        found = None
        for j in range(i + 1, len(words)):
            if (words[j]["startMs"] - words[i]["startMs"]) / 1000 > RETAKE_WINDOW_S:
                break
            n = 0
            while j + n < len(words) and i + n < j and norm[i + n] == norm[j + n]:
                n += 1
            if n >= RETAKE_MIN_WORDS:
                found = j
                break
        if found is None:
            i += 1
            continue
        text = " ".join(w["text"] for w in words[i:found])
        cuts.append({"startMs": words[i]["startMs"], "endMs": words[found]["startMs"],
                     "reason": "retake", "text": text, "apply": True})
        i = found
    return cuts


def merge(cuts):
    out = []
    for c in sorted(cuts, key=lambda c: c["startMs"]):
        if out and c["startMs"] <= out[-1]["endMs"]:
            last = out[-1]
            last["endMs"] = max(last["endMs"], c["endMs"])
            last["reason"] = "+".join(dict.fromkeys(last["reason"].split("+") + c["reason"].split("+")))
            last["text"] = " / ".join(t for t in (last["text"], c["text"]) if t)
            last["apply"] = last["apply"] and c["apply"]
        else:
            out.append(dict(c))
    return out


def propose(video, words_path, noise_db=-35, min_silence=0.35, pad=0.08):
    words = spoken(json.load(open(words_path, encoding="utf8")))
    silences, duration = detect_silences(video, noise_db, min_silence)
    cuts = []
    for s, e in silences:
        a = 0.0 if s <= 0.01 else s + pad      # head and tail silence go entirely
        b = duration if e >= duration - 0.01 else e - pad
        if b - a >= 0.1:
            cuts.append({"startMs": round(a * 1000), "endMs": round(b * 1000),
                         "reason": "silence", "text": "", "apply": True})
    for w in words:
        if normalize(w["text"]) in FILLERS:
            cuts.append({"startMs": w["startMs"], "endMs": w["endMs"], "reason": "filler",
                         "text": w["text"], "apply": True})
    cuts += find_retakes(words)
    # Voice with no transcribed word over it is usually a filler whisper dropped. Uncertain: off by default.
    voiced = complement([(s, e) for s, e in silences], duration)
    for a, b in voiced:
        cursor = a
        for w in words:
            ws, we = w["startMs"] / 1000, w["endMs"] / 1000
            if we <= a or ws >= b:
                continue
            if ws - cursor >= 0.3:
                cuts.append({"startMs": round(cursor * 1000), "endMs": round(ws * 1000),
                             "reason": "unworded-voice", "text": "", "apply": False})
            cursor = max(cursor, we)
    cuts = merge(cuts)
    out = os.path.splitext(video)[0] + ".cuts.json"
    json.dump({"source": os.path.basename(video), "fps": FPS, "cuts": cuts}, open(out, "w", encoding="utf8"),
              ensure_ascii=False, indent=2)
    removed = sum(c["endMs"] - c["startMs"] for c in cuts if c["apply"]) / 1000
    print(f"{'#':>3} {'from':>6} {'to':>6} {'sec':>5}  apply  reason          text")
    for k, c in enumerate(cuts):
        f0, f1 = round(c["startMs"] / 1000 * FPS), round(c["endMs"] / 1000 * FPS)
        print(f"{k:>3} {f0:>6} {f1:>6} {(c['endMs'] - c['startMs']) / 1000:>5.2f}  {'yes' if c['apply'] else 'no ':5}  "
              f"{c['reason']:<15} {c['text'][:60]}")
    print(f"{duration:.2f}s take, {removed:.2f}s marked to cut -> {duration - removed:.2f}s. Wrote {out}")


def complement(intervals, duration):
    keep, cursor = [], 0.0
    for a, b in sorted(intervals):
        if a > cursor:
            keep.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < duration:
        keep.append((cursor, duration))
    return keep


def keep_segments(cuts, duration):
    """Frame-snapped segments to keep; anything shorter than 2 frames is dropped."""
    snap = lambda t: round(t * FPS) / FPS
    active = [(snap(c["startMs"] / 1000), snap(c["endMs"] / 1000)) for c in cuts if c["apply"]]
    return [(a, b) for a, b in complement(active, snap(duration)) if b - a >= 2 / FPS]


def apply(video, cuts_path=None):
    cuts_path = cuts_path or os.path.splitext(video)[0] + ".cuts.json"
    cuts = json.load(open(cuts_path, encoding="utf8"))["cuts"]
    duration = probe_duration(video)
    segments = keep_segments(cuts, duration)
    fade = 0.01  # 10 ms fades stop clicks at every join
    lines = []
    for i, (a, b) in enumerate(segments):
        lines.append(f"[0:v]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS[v{i}];")
        lines.append(f"[0:a]atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={fade},afade=t=out:st={max(0, b - a - fade):.4f}:d={fade}[a{i}];")
    lines.append("".join(f"[v{i}][a{i}]" for i in range(len(segments))) + f"concat=n={len(segments)}:v=1:a=1[v][a]")
    script = os.path.join(tempfile.mkdtemp(), "cut.txt")
    open(script, "w").write("\n".join(lines))
    out = os.path.splitext(video)[0] + ".cut.mp4"
    # "-/option file" reads the value from a file (FFmpeg 7.1+; -filter_complex_script is gone in 8+).
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-/filter_complex", script,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", out], check=True)
    expected = sum(b - a for a, b in segments)
    got = probe_duration(out)
    print(f"{len(segments)} segments, expected {expected:.3f}s, got {got:.3f}s "
          f"({'ok' if abs(got - expected) < 2 / FPS else 'MISMATCH'}). Wrote {out}")


def selftest():
    w = lambda t, s: {"text": t, "startMs": s, "endMs": s + 300}
    words = [w("Hoy", 0), w("vamos", 400), w("a", 800), w("ver", 1200),
             w("Hoy", 2000), w("vamos", 2400), w("a", 2800), w("ver", 3200), w("Claude.", 3600)]
    r = find_retakes(words)
    assert len(r) == 1 and (r[0]["startMs"], r[0]["endMs"]) == (0, 2000), r
    assert not find_retakes([w("más", 0), w("rápido", 300), w("más", 600), w("lento", 900)])
    cuts = [{"startMs": 1000, "endMs": 2000, "apply": True}, {"startMs": 5000, "endMs": 6000, "apply": False}]
    segs = keep_segments(cuts, 4.0)
    assert segs == [(0.0, 1.0), (2.0, 4.0)], segs
    assert merge([{"startMs": 0, "endMs": 10, "reason": "a", "text": "", "apply": True},
                  {"startMs": 5, "endMs": 20, "reason": "b", "text": "", "apply": True}])[0]["endMs"] == 20
    print("selftest ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    opts = {k.lstrip("-").replace("-", "_"): float(v) for k, v in zip(args[::1], args[1:]) if k.startswith("--")}
    pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or not args[i - 1].startswith("--"))]
    if pos[:1] == ["propose"] and len(pos) >= 3:
        propose(pos[1], pos[2], opts.get("silence_db", -35), opts.get("min_silence", 0.35), opts.get("pad", 0.08))
    elif pos[:1] == ["apply"] and len(pos) >= 2:
        apply(pos[1], pos[2] if len(pos) > 2 else None)
    elif pos[:1] == ["selftest"]:
        selftest()
    else:
        print(__doc__)
