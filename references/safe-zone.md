# Safe zone

Instagram, TikTok and Shorts draw their UI over the edges of the video (account,
buttons, description), and the profile grid crops the cover. Anything touching
an edge gets covered or cut.

## Margins

| Format | Sides | Top | Bottom |
| --- | --- | --- | --- |
| Reels / TikTok / Shorts (1080x1920) | 108 | 150 | 340 |
| Feed portrait (1080x1350) | 108 | 80 | 80 |
| Feed square (1080x1080) | 135 | 80 | 80 |
| YouTube (1920x1080) | 96 | 54 | 54 |

- The margins apply to text, cards, icons, hooks and captions. The video and
  grounds still go full frame.
- **Never comply by shrinking the video or adding bars.** Shrink and centre the
  graphic instead (a panel at 80 % inside the zone).
- **Bottom 340 px is the minimum**: the description and buttons live there. A
  long description or an ad takes Meta's stricter margins, top 14 % and bottom
  35 % (about 270 and 670 px): `safe-zone.py --ads`.
- **Grid crop.** The profile grid shows the reel at 4:5, about y285 to y1635.
  Combined with the UI margins, a 1080x1920 reel keeps what matters in
  **x108-972, y285-1580**.
- **Cover.** The profile shows the cover at 3:4, cropping about 240 px top and
  bottom: its title goes in the centre 1080x1440.

## Check

After each range render (SKILL step 6):

```bash
python scripts/safe-zone.py public/recordings/name.mp4 "$TMPDIR/check" [--offset F] [--ads]
```

It diffs each check frame against the source take at the same frame (plus
`--offset`, the `trimBefore` of the video in frames), so whatever differs is a
graphic, and prints `OUT OF ZONE f<frame>: <margin>: <px>, box x..-.. y..-..`
for each margin it touches. A full-frame graphic (layout 3) changes the whole
frame; the script says so, and those frames are checked by eye on a guides sheet:

```bash
ffmpeg -v error -i "$TMPDIR/check/element-<f>.jpeg" -vf "drawbox=0:0:1080:150:red@0.35:fill,\
drawbox=0:1580:1080:340:red@0.35:fill,drawbox=0:0:108:1920:red@0.35:fill,\
drawbox=972:0:108:1920:red@0.35:fill,drawbox=0:285:1080:1350:yellow@0.8:4" guides.png
```

Red is covered by the UI, the yellow box is the grid crop. Ignore a graphic that
crosses a margin while it enters or leaves; only a resting one counts.
