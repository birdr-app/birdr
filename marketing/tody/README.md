# Tody

Tody, a Tody Motmot (*Hylomanes momotula*), is the Motmot mascot and replaces Bertie.
The full brand guide (colours, type, components, where each mood is used) is the
Motmot design system artifact; the source images also live in the Figma file
"Mottie – Motmot mascot".

- `masters/` — the generated 1024×1024 originals on white, plus `tody-app-icon.png`
  (head and shoulders on #10201B, square; the stores round the corners).
  `tody-head.png` is the same head without the background, used for the favicons,
  web app icons and the site header (the apple-touch-icon puts it on #FAF7F2).
- `cutout/` — the moods with the background removed: PNG (768px on the long side)
  and WebP for the app and the web.

| Mood | File | Replaces Bertie's |
| --- | --- | --- |
| Hello | `tody-hello` | flock-invite |
| Birding | `tody-birding` | start-game |
| Celebrates | `tody-correct` | success |
| Missed it | `tody-wrong` | failed |
| Thinking | `tody-thinking` | waiting |
| Under pressure | `tody-stressed` | stressed, survival |
| Champion | `tody-champion` | leaderboard |
| Asleep | `tody-sleeping` | maintenance |

Website poses, used on the marketing site:

| Pose | File | Used for |
| --- | --- | --- |
| Listening (headphones) | `tody-listening` | Photo, sound and video quizzes |
| Explorer (map and globe) | `tody-explorer` | Country Challenge, quizzes by country |
| Studying (field guide) | `tody-studying` | My Tricky Birds |
| Flock (three Todys) | `tody-flock` | Flocks and multiplayer |
| Peeking | `tody-peeking` | Decoration on the edge of a band or card |
| Flying | `tody-flying` | Decoration |

Web copies (600px WebP, plus the app icon at 64/128/256px and the wordmark SVGs) are in
`app/public/images/motmot/`, served at `/images/motmot/`.

## Making a new mood

Generate with this description word for word and only change the pose:

> Mascot illustration of "Tody", a cute cartoon Tody Motmot (Hylomanes momotula). Painterly digital storybook illustration with soft shading, visible feather texture and warm natural light, polished mobile game mascot style. Character (keep exactly): chubby, round, big-headed chibi proportions; rich chestnut-rufous cap covering crown and nape; broad black mask through the eyes; short bright turquoise-blue stripe just above and behind each eye; clean white line along the lower edge of the mask; whitish throat; soft olive-green to buff underparts with a paler belly; bright green back and wings; short plain green tail with no rackets; small slightly broad black bill; big expressive dark eyes with white highlights. No clothes, no hat. POSE: … Full body, centred, plain white background, no text.

Save the original in `masters/`, then cut it out:

```bash
python3 marketing/tody/cutout.py marketing/tody/masters marketing/tody/cutout
```

The script flood-fills the white background from the edges, so keep the pose off the image border.
It also processes the app icon; delete `cutout/tody-app-icon.png` afterwards.
