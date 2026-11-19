# Advanced birding: North-West Europe (`nw-europe-advanced`)

The step after the beginners courses (`nl-beginners`, `uk-beginners`; see
`docs/courses/netherlands/README.md` and `docs/courses/united-kingdom/README.md` for the idea and the
lesson format, which are the same here). For birders who already know Chiffchaff from Willow Warbler and
Dunlin from Little Stint: group-by-group identification, seasons and migration, strays, female-only duck
rounds, calls combined with photos, and a lot of repetition. Forty lessons in eight blocks of five: lessons
1-4 of every block teach 6-8 cards, lesson 5 is a review (`kind: "review"`, no cards). Lesson 40 is the final
exam. Ten countries: UK, IE, NL, BE, DE, FR, DK, NO, SE, FI.

- Lesson files: `jizz/courses/data/nw-europe-advanced/lesson-NN-*.json` plus `lookalikes.json` (114 groups).
- Registered in `jizz/courses/content.py` (`COURSES`); website `/site/advanced-bird-course/`.
- Photo picker for admins: `/course-photos?course=nw-europe-advanced`.
- Content only: no code was changed for this step.

## Numbers

- 40 lessons: 32 teaching lessons (240 cards, **231 different species**) and 8 reviews (weeks 5, 10, ..., 35, and
  the final exam in week 40).
- A card is one species in one plumage; the same species returns in another lesson in a different plumage
  (e.g. Herring Gull adult in week 1, first-winter in week 2). **One species appears only once per lesson**
  because the photo picks are keyed by (week, species).
- Plumage text on every card; `plumage_filter` on 128 cards, `plumage_required: true` on the lessons that
  depend on it (weeks 1-4, 11-14, 17-19, 21-24, 28, 33, 38).

## Lessons

| Week | Lesson | Season | Cards (plumage) / quiz |
|---|---|---|---|
| 1 | Reading a gull | winter | Black-headed Gull (first-winter), Common Gull (adult), Herring Gull (adult), Lesser Black-backed Gull (adult), Great Black-backed Gull (adult), Mediterranean Gull (adult, non-breeding) |
| 2 | Big gulls and their young | winter | Herring Gull (first-winter), Lesser Black-backed Gull (first-winter), Great Black-backed Gull (first-winter), Yellow-legged Gull (adult), Caspian Gull (adult), Common Gull (first-winter) |
| 3 | White-wingers and small gulls | winter | Iceland Gull (first-winter), Glaucous Gull (first-winter), Black-legged Kittiwake (adult), Little Gull (first-winter), Ring-billed Gull (adult), Slender-billed Gull (adult), Sabine's Gull (juvenile) |
| 4 | Terns | summer | Sandwich Tern (adult), Common Tern (adult), Arctic Tern (adult), Roseate Tern (adult), Little Tern (adult), Black Tern (adult, non-breeding), White-winged Black Tern (juvenile), Caspian Tern (adult) |
| 5 | Review: gulls and terns | any | Quiz of weeks 1, 2, 3, 4 |
| 6 | Chiffchaff, Willow and Wood | spring | Common Chiffchaff (adult), Willow Warbler (adult), Wood Warbler (adult), Iberian Chiffchaff (adult), Western Bonelli's Warbler (adult), Goldcrest (adult), Common Firecrest (adult) |
| 7 | Siberian leaf warblers | autumn | Yellow-browed Warbler (adult), Pallas's Leaf Warbler (adult), Hume's Leaf Warbler (adult), Arctic Warbler (adult), Greenish Warbler (adult), Radde's Warbler (adult), Dusky Warbler (adult) |
| 8 | Reed and marsh warblers | summer | Common Reed Warbler (adult), Marsh Warbler (adult), Sedge Warbler (adult), Great Reed Warbler (adult), Blyth's Reed Warbler (adult), Paddyfield Warbler (adult), Aquatic Warbler (adult), Common Grasshopper Warbler (adult) |
| 9 | Tree warblers and Sylvias | summer | Icterine Warbler (adult), Melodious Warbler (adult), Booted Warbler (adult), Eastern Olivaceous Warbler (adult), Garden Warbler (adult), Eurasian Blackcap (adult male), Lesser Whitethroat (adult), Common Whitethroat (adult male) |
| 10 | Review: warblers | any | Quiz of weeks 6, 7, 8, 9, 1, 2, 3, 4 |
| 11 | Dunlin, stints and small sandpipers | autumn | Dunlin (adult, non-breeding), Little Stint (juvenile), Temminck's Stint (adult), Curlew Sandpiper (juvenile), Sanderling (adult, non-breeding), Pectoral Sandpiper (juvenile) |
| 12 | Redshanks and sandpipers | autumn | Common Redshank (adult), Spotted Redshank (adult, non-breeding), Common Greenshank (adult), Green Sandpiper (adult), Wood Sandpiper (adult), Common Sandpiper (adult), Ruddy Turnstone (adult, non-breeding) |
| 13 | Plovers, godwits and Whimbrel | any | Common Ringed Plover (adult), Little Ringed Plover (adult), Kentish Plover (adult), Grey Plover (adult, non-breeding), European Golden Plover (adult, non-breeding), Black-tailed Godwit (adult), Bar-tailed Godwit (adult, non-breeding), Eurasian Whimbrel (adult) |
| 14 | Phalaropes, Ruff, Knot and snipe | autumn | Red-necked Phalarope (juvenile), Grey Phalarope (adult, non-breeding), Ruff (juvenile), Red Knot (adult, non-breeding), Purple Sandpiper (adult, non-breeding), Jack Snipe (adult), Common Snipe (adult), Pied Avocet (adult) |
| 15 | Review: waders | any | Quiz of weeks 11, 12, 13, 14, 6, 7, 8, 9 |
| 16 | Seawatching: shearwaters and petrels | autumn | Northern Fulmar (adult), Manx Shearwater (adult), Balearic Shearwater (adult), Sooty Shearwater (adult), Great Shearwater (adult), Cory's Shearwater (adult), European Storm Petrel (adult), Leach's Storm Petrel (adult) |
| 17 | Skuas, Gannet and Kittiwake | autumn | Great Skua (adult), Arctic Skua (adult), Pomarine Skua (adult), Long-tailed Skua (juvenile), Northern Gannet (juvenile), Black-legged Kittiwake (juvenile) |
| 18 | Auks and divers | winter | Common Guillemot (adult, non-breeding), Razorbill (adult, non-breeding), Atlantic Puffin (adult, non-breeding), Black Guillemot (adult, non-breeding), Little Auk (adult, non-breeding), Red-throated Diver (adult, non-breeding), Black-throated Diver (adult, non-breeding), Great Northern Diver (adult, non-breeding) |
| 19 | Seaduck, Shag and Cormorant | winter | Common Eider (adult male), Common Scoter (adult male), Velvet Scoter (adult male), Surf Scoter (adult male), Long-tailed Duck (adult male), King Eider (adult male), European Shag (adult), Great Cormorant (adult) |
| 20 | Review: seabirds from land | any | Quiz of weeks 16, 17, 18, 19, 11, 12, 13, 14 |
| 21 | Female dabbling ducks | winter | Mallard (adult female), Gadwall (adult female), Eurasian Wigeon (adult female), Northern Pintail (adult female), Eurasian Teal (adult female), Garganey (adult female), Northern Shoveler (adult female) |
| 22 | Female diving ducks | winter | Tufted Duck (adult female), Greater Scaup (adult female), Common Pochard (adult female), Ferruginous Duck (adult female), Red-crested Pochard (adult female), Ring-necked Duck (adult female), Common Goldeneye (adult female) |
| 23 | Eclipse drakes and sawbills | autumn | Mallard (adult male, eclipse), Northern Shoveler (adult male, eclipse), Garganey (adult male, eclipse), Eurasian Wigeon (adult male, eclipse), Goosander (adult female), Red-breasted Merganser (adult female), Smew (adult female) |
| 24 | Geese and swans | winter | Greater White-fronted Goose (adult), Taiga Bean Goose (adult), Tundra Bean Goose (adult), Pink-footed Goose (adult), Lesser White-fronted Goose (adult), Red-breasted Goose (adult), Whooper Swan (adult), Bewick's Swan (adult) |
| 25 | Review: ducks and geese | any | Quiz of weeks 21, 22, 23, 24, 16, 17, 18, 19 |
| 26 | Raptors in flight | autumn | Common Buzzard (adult), Rough-legged Buzzard (adult), European Honey-buzzard (adult), Western Marsh Harrier (adult female), Hen Harrier (adult female), Montagu's Harrier (adult male), Osprey (adult), Black Kite (adult) |
| 27 | Pipits and wagtails | any | Meadow Pipit (adult), Tree Pipit (adult), Eurasian Rock Pipit (adult), Water Pipit (adult, non-breeding), Red-throated Pipit (adult), Western Yellow Wagtail (adult male), Grey Wagtail (adult male), Pied Wagtail / White Wagtail (adult) |
| 28 | Larks and buntings | winter | Eurasian Skylark (adult), Woodlark (adult), Shore Lark (adult, non-breeding), Snow Bunting (adult, non-breeding), Lapland Bunting (adult, non-breeding), Corn Bunting (adult), Cirl Bunting (adult male), Common Reed Bunting (adult male) |
| 29 | Chats, flycatchers and Ring Ouzel | spring | Common Redstart (adult male), Black Redstart (adult male), Whinchat (adult male), European Stonechat (adult male), Northern Wheatear (adult male), Spotted Flycatcher (adult), European Pied Flycatcher (adult male), Ring Ouzel (adult male) |
| 30 | Review: field birds | any | Quiz of weeks 26, 27, 28, 29, 21, 22, 23, 24 |
| 31 | Pratincoles and rare waders | autumn | Collared Pratincole (adult), Black-winged Pratincole (adult), Black-winged Stilt (adult), Eurasian Dotterel (adult), Broad-billed Sandpiper (adult), Marsh Sandpiper (adult), Terek Sandpiper (adult) |
| 32 | Eastern vagrants | autumn | Siberian Accentor (adult), Red-flanked Bluetail (adult female), Richard's Pipit (adult), Olive-backed Pipit (adult), Little Bunting (adult), Rustic Bunting (adult), Red-breasted Flycatcher (adult), Brown Shrike (adult) |
| 33 | American vagrants | autumn | White-rumped Sandpiper (juvenile), Baird's Sandpiper (juvenile), Buff-breasted Sandpiper (juvenile), American Golden Plover (juvenile), Lesser Yellowlegs (juvenile), Long-billed Dowitcher (juvenile), Semipalmated Sandpiper (juvenile), Wilson's Phalarope (juvenile) |
| 34 | Southern overshoots and autumn falls | spring | Common Hoopoe (adult), European Bee-eater (adult), Woodchat Shrike (adult), Squacco Heron (adult), Glossy Ibis (adult), Eastern Subalpine Warbler (adult male), Common Rosefinch (adult male), Eurasian Wryneck (adult) |
| 35 | Review: strays | any | Quiz of weeks 31, 32, 33, 34, 26, 27, 28, 29 |
| 36 | Calls and night migration | autumn | Water Rail (adult), Corncrake (adult), Spotted Crake (adult), Common Quail (adult), Eurasian Nightjar (adult), Eurasian Woodcock (adult), Long-eared Owl (adult), Tawny Owl (adult) |
| 37 | Bad photos and jizz | any | Eurasian Sparrowhawk (adult), Eurasian Goshawk (adult), Peregrine Falcon (adult), Eurasian Hobby (adult), Merlin (adult), Common Kestrel (adult), Common Cuckoo (adult), Alpine Swift (adult) |
| 38 | Mixed plumages: finches, shrikes and waxwings | winter | Brambling (adult male, non-breeding), Twite (adult), Redpoll (adult), Common Crossbill (adult female), Hawfinch (adult), Bohemian Waxwing (adult), Great Grey Shrike (adult), Red-backed Shrike (adult female) |
| 39 | Marsh and Willow Tit, woodpeckers and treecreepers | any | Marsh Tit (adult), Willow Tit (adult), Crested Tit (adult), Coal Tit (adult), Lesser Spotted Woodpecker (adult male), Middle Spotted Woodpecker (adult), Black Woodpecker (adult male), Short-toed Treecreeper (adult) |
| 40 | Final exam | any | Quiz of all 32 teaching weeks |

Blocks: 1 gulls and terns, 2 warblers, 3 waders, 4 seabirds from land (autumn seawatching), 5 ducks and
geese (female and eclipse rounds), 6 field birds, 7 strays, 8 pro skills.

### Differences from the brief's outline

- Because of the one-card-per-species-per-lesson rule, the gull age series is spread over weeks 1-3
  (adults in week 1, first-winters of the same species in week 2, white-wingers in week 3). Sabine's Gull is
  taught once, in week 3 as a juvenile, and the Kittiwake appears twice (adult, week 3; juvenile, week 17).
- Week 17 has six cards, not seven or eight: four skuas, a juvenile Gannet and a juvenile Kittiwake.
  Weeks 1, 2 and 11 also have six.
- Block 8 teaches new species in every lesson instead of re-using old ones: week 36 (night and shy birds,
  mostly sound), week 37 (shape and jizz: hawks, falcons, Cuckoo, Alpine Swift; the "bad photos" idea is in the
  intro and the quiz expects poor photos), week 38 (the "mixed plumage gauntlet": the female Crossbill and
  female Red-backed Shrike on purpose), week 39 (the "every bird" leftovers: Marsh/Willow Tit, woodpeckers,
  Short-toed Treecreeper). Week 40 is a 40-question exam over all 32 teaching weeks.
- Siberian Accentor, Pallas's, Hume's, Arctic, Greenish, Radde's and Dusky Warbler are the "Siberian" set;
  Cetti's Warbler, Savi's Warbler, Pallid Swift and several other southern birds did not make the list.
- Lesser and Common Whitethroat use the genus name the database has (`Curruca`). Redpoll is one species (the database lumps Lesser Redpoll and Arctic Redpoll). Cory's Shearwater is species
  11039, the Herring Gull is 11038, Bewick's Swan is 97, Short-toed Treecreeper 8481.

## Quiz settings

Every teaching lesson has `quiz.modes` (`photo`, `photo_sound`, `sound`; the numbers add up to `questions`),
mostly photo and photo+sound with a little sound-only; the voice-led lessons (warblers, waders, week 36) lean
more on sound. Review lessons use all questions for review (`review_questions` = `questions`; 15 in week 5,
20 in weeks 10-35, 40 in week 40). `review_from` of a teaching lesson is the previous two teaching weeks plus
the same slot of the previous block; of a review lesson the weeks of its block plus the previous block.

## Where things came from

- **Species:** ids and Latin names are taken from the database `Species` table; a check script confirms that
  every `species_id` has the `latin` in the file (it ran with no mismatches).
- **Texts:** written from my own knowledge, not from a source. Facts are checked against what I know only. A
  birder who knows the region should read it, in particular the calls of the rarities (Hume's, Iberian
  Chiffchaff, Radde's, Terek), the winter and passage dates, and the "where and when" lines.
- **`where_when` and `where_data`:** `where_when` is text per country (which of the ten see it, when, how
  often). `where_data` repeats the frequency tier and `peak_season` of that species from
  `jizz/data/commonness_<CC>.csv` for the ten countries. The tiers come from eBird models, so many regular
  rarities (Yellow-legged Gull, Caspian Gull, Wood Warbler) show as "very rare" or have no row; the text
  follows what a birder expects, the data is there for reference.
- **Photos:** `media.card` (3) and `media.quiz` (8) per card are visible, non-duplicate, non-rejected photos
  of that species. Order: photos with a matching `MediaPlumage` label first, then photos that passed review
  (`MediaReview` approved), then the rest. Where a card has a `plumage_filter`, labelled photos of a
  conflicting plumage are left out.
- **Sounds:** `sound.chosen` holds up to three xeno-canto recordings per bird (one call and one song where
  the bird has both, `sound.type` says which). They were chosen from the recordings in the database using the
  details from the xeno-canto API (type, quality, country, length, background species): quality A first, no
  background species, the ten countries in the order UK, IE, NL, BE, DE, FR, DK, NO, SE, FI, then the rest of
  Europe, then elsewhere; different recordists. Nobody has listened to them.

## What is not verified (read before use)

1. **Plumage of the photos.** Only the cards of the 128 filtered birds with 7 or more photos that carry a
   matching `MediaPlumage` label (28 cards) are verified. The other 100 cards were filled with approved but
   unlabelled photos and may show the wrong plumage (a "female Mallard" card is mostly males; first-winter
   gulls are mostly adults). Per card `media_status` says how many labelled matches there were. All
   female and eclipse duck cards (weeks 21-23: 21 cards) have **no** or one labelled photo, and weeks 11 and 18
   have almost none. `manage.py check_course_plumage nw-europe-advanced` reports 1,001 of 1,407 filtered photos
   without a matching label as of today; this is expected until the plumage labelling has run, after which the
   photos must be picked again (picker, or re-run the seeding).
   Photos of unfiltered cards (most passerines) are approved, adult-labelled where possible, and were not
   looked at one by one.
2. **Sounds.**
   - Picks were made from a production dump. The audio that was missing there was then scraped **on the
     server** (xeno-canto, 20 recordings each): Little Ringed Plover and Kentish Plover (week 13), Eurasian
     Dotterel (31), Common Hoopoe (34), Eurasian Goshawk (37); plus 12 quality-A recordings each for Grey Plover
     (13) and Grey Wagtail (27). The new prod media ids are in the files. (The scraper itself searches under a
     newer genus name than xeno-canto uses for the plovers, Dotterel and Goshawk; those were fetched under the
     old name.) These ids do not exist in a local copy made before the scrape.
   - No quality-A recording exists on xeno-canto for Iceland Gull (week 3) or Siberian Accentor (week 32);
     B recordings are used.
   - All recordings of Herring Gull (weeks 1, 2), Spotted Flycatcher (29) and Red-flanked Bluetail (32), and some
     of Grasshopper Warbler (8) and Short-toed Treecreeper (39) are hidden in the dump
     (`hidden_locally: true`): check why before shipping.
   - Recordings are long (mostly 20-90 s); no start/end times are stored.
3. **Birds without photos or sounds.** Every card has at least 7 photos (European Honey-buzzard has the fewest). Every bird has at least one recording.
4. **Texts.** The ID features and the call descriptions are mine and unchecked; the quiz distractors come from
   `lookalikes.json`. The intro texts mention a few things (the 2016 Siberian Accentor arrival, winter Blackcaps,
   Pied Avocet history) from memory.

## Before it goes live

1. Run the plumage labelling (`label_media_plumage`, then the picker's confirm action) for the species of the
   plumage-required lessons, then re-pick and run `check_course_plumage nw-europe-advanced` until it is clean.
   Start with weeks 21-23 (female and eclipse ducks), 2, 11 and 18.
2. Listen to the recordings that were scraped last (week 13, 27, 31, 34, 37).
3. Walk through the lessons in the photo picker (`/course-photos?course=nw-europe-advanced`); the rarities of
   weeks 7, 31-34 have the thinnest choice.
4. Listen to the recordings (especially the rarities) and trim the long ones.
5. Have a birder from the region read the texts.
