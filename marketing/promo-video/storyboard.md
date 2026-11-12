# Motmot promo video — storyboard & script

**Target:** ~75 s, 16:9 (YouTube) + 9:16 cut (Shorts). English VO, burned-in captions (works muted).
**Tone:** friendly, curious, a bit playful. Mascot (Tody) cameos on transitions.
**Music:** upbeat acoustic/light-electronic instrumental (Suno), ducked under VO. Optional birdsong layer.
**Voice-over:** Suno (newer versions also do speech, which keeps music and VO in one tool), ElevenLabs, or your own voice. Generate the VO separately from the music so you can duck and time it against the clips.

| # | Time | Visual (screen grab) | On-screen text | Voice-over |
|---|------|----------------------|----------------|------------|
| 1 | 0–6 s | Hook: quiz question, bird photo, 4 answers. Finger taps a wrong one, then the right one → green. | "Can you name this bird?" | "Can you name this bird? Most of us can't. Not yet." |
| 2 | 6–12 s | Logo + Tody, app icon, tagline. | "Motmot — learn to identify birds yourself" | "Motmot doesn't tell you what a bird is. It teaches you to see it yourself." |
| 3 | 12–24 s | New game screen: pick country, level (Beginner → Expert), media (photo / sound / video). Then quiz with a photo, then a sound question. | "Photos. Sounds. Video." / "Any country. 5 levels." | "Practise with real photos, sounds and video, from any country, at the level that suits you." |
| 4 | 24–34 s | Game results / review screen, then My Tricky Birds (confused pairs). | "Learn from every mistake" | "Every miss is remembered. Motmot turns your tricky birds into focused practice." |
| 5 | 34–44 s | Checklist screen, species ticking off. | "Build your checklist" | "Every bird you recognise gets ticked off your personal checklist." |
| 6 | 44–56 s | Journey / Country Challenge path, level-up celebration. | "Level up through your country's birds" | "Follow a path from the easy birds in your garden to the hardest lookalikes." |
| 7 | 56–68 s | Flock / league / live multiplayer: leaderboard, friends, countdown. | "Play with friends" / "Daily & weekly challenges" | "Challenge friends, join a flock with your bird club, or take on the national league." |
| 8 | 68–75 s | End card: Tody, store badges, URL, QR. | "Free on iPhone, Android & web — motmot.club" | "Motmot. Free on iPhone, Android and the web. Learn birds. Play with friends." |

## Screens to capture
1. Quiz question (photo) with answer reveal (correct + wrong)
2. Quiz question (sound)
3. New game setup (country, level, media)
4. Game results / answer review
5. My Tricky Birds
6. My Checklist
7. Country Journey path + level celebration
8. Flock / League leaderboard
9. Home screen (opening / closing)

Existing stills to reuse as fallbacks: `marketing/screenshots/*.png`, mascot art in `mobile/assets/birdr-*.png`.

## Deliverables / tooling
- Recording: `xcrun simctl io <udid> recordVideo clip.mov` (iPhone 18 Pro simulator), or screen record on a real phone.
- Edit: CapCut / DaVinci Resolve / Screen Studio, or Remotion for a scripted, repeatable version.
- Music: Suno prompt — "upbeat light acoustic pop, ukulele and soft percussion, optimistic, nature documentary meets app promo, instrumental, 75 seconds".
