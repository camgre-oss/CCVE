# CCVE: Camgre Claude Video Editor

Add-ons for the `remotion-reel` Claude skill: the pieces that turn it into a
full talking-head reel editor. Claude edits the reel in code (Remotion, ffmpeg,
whisper.cpp); CCVE adds the rough cut, safety checks and delivery steps the base
skill does not have.

This repository contains **only the CCVE additions**. The base skill is
Michael Ly's `remotion-reel` (millee.md), distributed through his guide:
<https://milleemd.com/guides/claude-x-remotion/>. Get it there; it is not
redistributed here.

## What CCVE adds

| Piece | What it does |
| --- | --- |
| `scripts/autocut.py` | Rough cut of a raw take. Proposes cuts for silences, fillers, retakes (the same 3+ words said again) and unworded voice, as a reviewable `take.cuts.json`; `apply` renders `take.cut.mp4`. |
| `scripts/safe-zone.py` | Diffs rendered check frames against the source take and flags any graphic under Instagram's UI margins. |
| `references/safe-zone.md` | UI margins per format (Reels, feed 4:5, square, YouTube), the grid crop, ad margins and the check. |
| `scripts/contrast.py` | WCAG contrast of every pair of brand colours; pairs under 3:1 are forbidden. |
| `scripts/beat-grid.py` | BPM and beat frames of a music bed, in composition frames, to land graphic hits on the beat. |
| `scripts/loudness.py` | Brings the final mp4 to -10 LUFS (reel loudness) without re-encoding the picture. |
| `patches/remotion-reel.patch` | Wires all of the above into the skill: step 2b (rough cut), the safe-zone check, the 3-round brand interview with contrast, the beat grid, and the delivery loudness step. |

## Install

1. Download the `remotion-reel` skill from the guide above and unzip it to
   `~/.claude/skills/remotion-reel/`.
2. From that folder, apply CCVE:

```bash
cd ~/.claude/skills/remotion-reel
git apply /path/to/CCVE/patches/remotion-reel.patch
cp /path/to/CCVE/scripts/*.py scripts/
cp /path/to/CCVE/references/safe-zone.md references/
```

3. Requirements: ffmpeg on PATH (FFmpeg 7.1 or newer), Python 3 with numpy
   (`python -m pip install numpy`).

The patch targets the skill version published on 2026-11-13. If `git apply`
reports a conflict, the base skill has changed: apply the hunks by hand.

## Check it works

```bash
python scripts/autocut.py selftest
python scripts/safe-zone.py selftest
python scripts/beat-grid.py selftest
python scripts/contrast.py "#0B0B0C" "#FFD60A" "#FFFFFF"
```

## Authors

- Byron Omar Freire Cantos (Camgre)
- Claude (Anthropic)

Base skill `remotion-reel` by Michael Ly (millee.md). Ideas for the safe zone,
contrast rule, beat grid and loudness target were adapted from the
"estudio-motion" HyperFrames skill shared in a reel.

## License

MIT for the CCVE additions in this repository (see `LICENSE`). The base
`remotion-reel` skill keeps its author's terms.
