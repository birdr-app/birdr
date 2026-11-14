# Trip prep

A feature that gets a birder ready for a trip to a country where they only know some of the birds.
Example: a European birder travelling to Sri Lanka. This is the plan for screens, the learning
flow, progress, the content per country and the scripts that make it.

**Status:** the content pipeline is built (`jizz/trips/`, commands `trip_prep_units`,
`trip_prep_texts`, `trip_prep_media`, `trip_prep_build`, writing guide `STYLE.md`) and Sri Lanka's
content is drafted in `jizz/trips/data/lk/` with shared texts in `jizz/trips/data/{groups,species}/`.
Seychelles (`sc/`, 55 species) and Uganda (`ug/`, 202 species) followed; their species lists are
hand-picked in `scope.json`, because eBird Status & Trends models too few of their birds for the
frequency cut. Their photos are reviewed (see `sc/report.md` and `ug/report.md`) and both are
published in `TRIPS`. Australia (`au/`, 293 species, hand-picked, plus six region packs, see `regions.md`) has all its texts in English and Dutch, its photos reviewed (see `au/` report in `au-photos.md`; a few look-alike picks wait for the owner's eye) and is published in `TRIPS` with the packs. A country folder that is not in `TRIPS` counts as a draft: the test suite checks
its texts and units, but not its photos.
Iberia (`iberia/`, Spain and Portugal as one trip like the Baltics, 223 species, hand-picked, 9 lookalike pairs, no endemics chapter) has its texts in English and Dutch and its photos picked by the owner. It is published in `TRIPS`, together with the Canary Islands region pack (`iberia-canaries/`, 21 species, 4 units). Madeira (`iberia-madeira/`, 12 species) and the Azores (`iberia-azores/`, 9 species) are published too. Their photos for Trocaz Pigeon, Madeira Firecrest, Madeira Chaffinch, Azores Bullfinch, Azores Chaffinch, Monteiro's Storm-Petrel and Cory's Shearwater were picked from unreviewed candidates (Monteiro's are in-hand ringing shots, since the bird is rarely photographed in flight). The picked photos still need approving in the media review page on production. The old ids `ES` and `ES-CANARIES` still work in the API (`TRIP_ALIASES`).
Colombia (`co/`, 379 species, hand-picked from an occurrence assessment of all 1,959 species) is a draft with five region packs: `co-caribbean` (73), `co-choco` (158), `co-andes` (112), `co-amazon` (187) and `co-llanos` (50). Texts in English and Dutch are complete and the build check shows 0 errors. Card and quiz photos were picked by review agents from contact sheets and are not approved on production; 17 species with no usable photo were left out of the scopes (see each `scope.json`). Published in `TRIPS` with the five packs; check the photos on `/trip-photos`.
Thailand (`th/`, 274 species, hand-picked from GBIF/eBird record counts, 55 units, one endemic) and the Baltics (`baltics/`, one trip over Estonia, Latvia and Lithuania via `countries` in `TRIPS`, 202 species, 38 units, hand-grouped: do not re-run `trip_prep_units` for it) have texts in English and Dutch, passed the build check and are published in `TRIPS`. Their photos were picked by review agents and are not approved on production; check them on `/trip-photos`. For Thailand do not re-run `trip_prep_media` before the picks are approved, it would overwrite them.
Cambodia (`kh/`, 259 species, 52 units, three endemics) and South Africa (`za/`, 334 species, 64 units, 19 endemics) are hand-picked the same way, have texts in English and Dutch, pass the build check and are published in `TRIPS`. Their `media.json` was written from review-agent picks and is not approved on production: do not re-run `trip_prep_media` for `KH` or `ZA`. Left out for lack of usable photos: Siamese Pied Starling and Hainan Blue Flycatcher (KH); White-backed Mousebird, Greater Honeyguide and Cape Parrot (ZA). `groups/honeyguides.json` is unused.
The texts still need a human review.

The web app has the screens (`app/src/pages/trip/`, routes `/trips`, `/trips/<cc>`, `.../families`,
`.../units/<slug>`, `.../endemics`, `.../lookalikes`), backed by `/api/trips/` (`jizz/trips/views.py`).
For a country close to home (Morocco for a Dutch birder) the screens skip what the player knows:
units whose birds are all known fold away on the trip home and count as done, a partly known unit
shows cards and quiz questions only for its new birds, and *Meet the families* gives a card only to
new groups (the known ones share one card). *Lookalikes from home* pairs trip birds with European
birds they can be taken for (`lookalikes/` and `scope.json`, see `STYLE.md`); Sri Lanka has 13 pairs.
The mobile app doesn't have the lookalikes or the folding yet. Unit quizzes are
stored as `trip_prep` games with score 0 (kept out of hiscores and best scores), so they count as
"known" everywhere. Not built yet: the `Trip` model (units done and cards seen live on the device for
now), the review screen for shaky birds, "closest bird you know" on cards, sounds, and the mobile app.

**Name:** *Trip prep* in menus; the screen title reads "Get ready for Sri Lanka" (NL: *Klaar voor
Sri Lanka*). Alternatives considered: "Bird briefing", "Destination".

## Decisions so far

- **Selected countries, not all countries.** Every country gets written content (group and species
  texts, an endemics chapter, chosen photos). First five: Costa Rica, Sri Lanka, Gabon, Madagascar,
  New Zealand. Adding a country is a repeatable pipeline of scripts plus a writing and review pass.
- **Earlier answers count.** A species answered correctly in any game, in any country, is "known".
- **Group texts adapt to the player's background.** "Wrens" means one bird to a European and
  eighty to an American; the text says so (see *Texts that know what you know*).
- **Endemics get their own chapter** per country.
- **No travel month in the first release.** See *Travel month* for what it would take; it is less
  than a new eBird integration.

## Learning approach

The order is: **know what kinds of birds live there → meet each kind's species → get quizzed →
review the mistakes.** Three rules:

1. **Start from what you know.** A European birder already knows herons, kingfishers and wagtails,
   but not bulbuls, babblers or sunbirds. Every screen separates "old friends" from "new to you".
2. **Show before you quiz.** You never get a question about a bird you haven't seen a card for.
3. **A wrong answer goes back in the queue.** A unit isn't scored. It's done once every bird in it
   has been answered right at least once. This matches the main measure, "correct at some point".

## What counts

- **Species in scope:** `CountrySpecies` with status `native` or `endemic`, and established
  `introduced` species, with frequency **abundant to uncommon**. Introduced birds matter: in New
  Zealand the Blackbird, Song Thrush and Common Myna are among the first birds you see. Rare and
  vagrant species stay out. A per-country `scope.json` can add or drop species by hand.
- **Progress:** identified species ÷ species in scope, counting answers from any game in any
  country. The checklist service already builds this "identified" set
  (`jizz/services/checklist.py`); it only needs to drop the per-country filter.
- **Endemics:** their own counter on the trip home screen, their own chapter, and a badge wherever
  they appear.

## Screens

### 1. Start a trip

Pick one of the countries that have Trip prep. A preview shows before starting:

> Sri Lanka: 250 regular species in 60 groups, 34 endemics.
> You already know 61 of them from other games. 23 groups are new to you.

### 2. Trip home: the main progress screen

```
 🇱🇰 Sri Lanka                    38 days to go
        ┌───────┐
        │  34%  │  85 / 250 species
        └───────┘
  Endemics 6/34 · Groups met 60/60 · Shaky 14

 [ Continue: Bulbuls 2/3 ▶ ]

 Meet the families            ✓ done
 Endemics of Sri Lanka        6/34  ▸
 Review my shaky birds (14)         ▸

 Groups
  Bulbuls          ████░░ 4/6
  Babblers         █░░░░░ 1/8
  Herons & egrets  █████▉ 12/13  (old friends)
  …
```

(Numbers are illustrations.)

### 3. Meet the families (the introduction)

One swipeable card per bird group: name, a short text (see *Texts that know what you know*), three
or four example photos, "6 species in Sri Lanka", and a tag: *new to you*, *old friend* or *false
friend*. New groups come first. A short family quiz follows: a photo, and you pick the group from
four.

Groups start from `SpeciesGroup` (the birder groups from eBird, translated into all eight languages)
rather than the scientific family; the country's `units.json` can rename, merge or split them.

### 4. Unit (the main loop)

The same shape as a course lesson: intro → species cards → quiz → result.

- A unit holds **4–7 species from one group**. Large groups are split in taxonomic order, so
  lookalikes end up in the same unit. Within a unit the commonest birds come first.
- **Species card:** chosen photos, name and Latin name, how common it is, the endemic badge, a sound
  button, the "look for" text, and **"Closest bird you know"**: a species from the same genus or
  group the player has identified before, picked at runtime.
- **Quiz:** about 8–10 questions with four options. Wrong options come from the same group plus
  earlier units. Each unit also asks 2–3 review questions from earlier units.
- **Test out:** when the player already knows most of a unit's birds: "You know 5 of 6, quick
  check?" goes straight to the quiz.
- **Only the new birds:** when the player knows some of a unit's birds, the cards and the quiz
  cover the new ones; the known ones still appear as wrong options. "Show all" brings them back.
- **Lookalikes from home:** one card per pair, the home bird next to the trip bird with two or three
  lines on how to tell them apart, then a quiz that shows either bird and asks which of the two it
  is. It comes after *Your first day*. For a country close to home this is the main chapter.

### 5. Group detail

A grid of the group's species, each in one of four states: not started (grey), cards seen,
identified (✓), shaky (last answer wrong, orange). Tapping a species opens its card.

### 6. Endemics chapter

See *Endemics chapter* below.

### 7. Review

A mixed quiz of learned birds, weighted towards the shaky ones. The one to play on the plane.

**Entry points:** a tile on the home page and an item in the menu. With more than one trip, a list
of trips.

## Ordering

1. Meet the families
2. **"Your first day"**: the 20 commonest birds in the country across all groups, so the first walk
   outside already pays off
3. Group units: new groups first, ordered by how common their birds are; old-friend groups later
4. Endemics chapter, available in parallel all along

## Texts that know what you know

A group text has parts, and the app picks which to show from the species the player has identified
(in any country). No "home region" setting is needed; the answers say it.

| Part | Shown when | Example (Costa Rica, Wrens) |
|---|---|---|
| `about` | The player knows no species in this group | "Small brown birds with barred wings and a cocked tail, heard far more often than seen." |
| `known` (generated) | The player knows one or more | "You know Eurasian Wren." |
| `here` | Always | "Costa Rica has 22 wrens. Most live low in dense forest; learn their songs." |
| `false_friend` | The player knows a *different* group with a similar name | New World Warblers, for someone who knows Old World warblers: "Not related to the warblers you know. These are colourful, active and often in mixed flocks." |

`about` is general and stored once per group (`SpeciesGroup.description_*`, empty today). `here` is
written per country. `false_friend` names the groups it reacts to, for example
`{"if_known": ["reed-warblers-and-allies", "leaf-warblers"], "text": {...}}`. Typical false friends:
New World warblers, American robins, New World vultures, the Australasian robins and wrens in New
Zealand.

Species texts work the same way in small: a general `look_for` (three points, stored once per
species, so Barn Swallow is written once) and an optional `here` line per country ("In Sri Lanka,
watch for Red-rumped Swallow alongside it").

## Endemics chapter

One chapter per country, in four parts:

1. **Why here:** a short text on why the country has its own birds (island, mountains, forest
   block) and how many there are.
2. **Where to find them:** the regions or habitats that hold most endemics (Sri Lanka's wet zone,
   the Talamanca highlands, Madagascar's eastern rainforest), as a few short cards. This is where the
   itinerary will later plug in.
3. **Endemic families:** where a whole family lives only here (Madagascar's vangas, couas, mesites
   and ground-rollers; New Zealand's kiwis and wattlebirds), a family card first.
4. **The birds:** units of about 6, then the quiz, like any unit. Endemics also stay in their normal
   group units, with the badge.

Some countries have few true endemics: Costa Rica has 8 in the database and Gabon 1. Their chapter
also covers **regional specialities**, birds you can only see in a small region across a border,
such as the Chiriquí highland birds shared with Panama or Lower Guinea forest birds. These get a
"Regional speciality" badge and come from a hand-made list in the country folder, since
`CountrySpecies` doesn't record them.

Open: rare endemics (many are local or hard to find) are in the chapter, but do they count towards
the main percentage? Suggested: they count towards the endemics counter only.

## The five countries

Counts from the local database (native, endemic and introduced species, before the rarity cut):

| Country | Species | Endemic | Groups | ≥3 photos | ≥3 *approved* photos | With sound |
|---|---|---|---|---|---|---|
| Sri Lanka | 357 | 34 | 70 | 357 | 110 | 330 |
| New Zealand | 236 | 73 | 46 | 235 | 46 | 209 |
| Madagascar | 243 | 107 | 53 | 240 | 51 | 223 |
| Costa Rica | 793 | 8 | 70 | 793 | 73 | 758 |
| Gabon | 598 | 1 | 81 | 587 | 89 | 531 |

Suggested order:

1. **Sri Lanka** as the pilot: small, a strong endemics story, and overlap with India later.
2. **New Zealand:** tests introduced birds and a high "already known" share for Europeans. Seabirds
   (albatrosses, petrels, shearwaters) are hard and may need their own chapter.
3. **Madagascar:** the endemics chapter is most of the course.
4. **Costa Rica:** the big one: hummingbirds, tanagers, tyrant flycatchers.
5. **Gabon:** forest birds that are heard more than seen. It leans on sounds, and the weakest photo
   set is likely.

Two data problems show up already:

- **Rarity isn't filled in for these countries locally.** Every native species has frequency `rare`,
  which is the fallback value. "Abundant to uncommon" would select nothing. Step 2 of the pipeline
  fixes this; production may be different, so check there first.
- **Few photos are approved.** Nearly every species has three or more photos, but only 10–30% have
  three approved ones. Photo review is the biggest single job per country.

## Adding a country: the pipeline

Content lives in the repo as JSON, like the courses (`jizz/courses/data/`), so every change is
reviewed in a diff and ships with the code:

```
jizz/trips/data/
  species/<ebird-code>.json      look_for texts, shared by all countries
  groups/<group-slug>.json       about and false_friend texts, shared by all countries
  lk/
    scope.json                   species added or dropped by hand, regional specialities
    units.json                   groups, unit splits, order, "Your first day"
    texts.json                   here texts for groups and species, endemics chapter
    media.json                   chosen card photos, quiz photos and sounds per species
    report.md                    output of the readiness check
```

Each step is a management command, except the writing (step 5), which is done by a Claude Code
session following a project skill and a style guide, like the Netherlands course. A
`trip-prep-add-country` skill runs the whole list in order, so adding a country is "run the skill
for GA, then review".

| # | Step | Command | Manual work |
|---|---|---|---|
| 1 | **Readiness check:** species by status and frequency, endemics, groups, photo and sound coverage, missing names in the eight languages | `trip_prep_check --country LK` → `report.md` | Read the report |
| 2 | **Rarity:** fill `CountrySpecies.frequency` from eBird Status & Trends | existing `provision_country_species_frequency --country LK --all-species` or `ebird_st_commonness` | Spot-check the commonest 30 against a field guide |
| 3 | **Scope and endemics:** compare the endemic list with a reference list; list regional specialities; mark established introduced species | `trip_prep_scope --country LK` writes a draft `scope.json` with suggestions | Accept or fix the suggestions |
| 4 | **Groups and units:** group in-scope species by `SpeciesGroup`, merge one-species groups into a neighbour or an "Odd ones out" unit, split large groups into 4–7 in taxonomic order, pick "Your first day" | `trip_prep_units --country LK` → `units.json` | Rename, merge and reorder |
| 5 | **Texts:** `about` and `false_friend` for groups that don't have them yet, `look_for` for species that don't have one yet, `here` texts, the endemics chapter. English first, then Dutch. Facts from Wikipedia and eBird, written in our own words (no copied field-guide text) | Claude Code session via the skill; `trip_prep_texts --missing --country LK` lists what's still empty | Review every text; this is the largest manual step |
| 6 | **Photos and sounds:** rank candidate photos per species (existing bird detection and predictions, size, earlier reviews), queue them in the media review page for this country, pick 3–4 card photos and a quiz set, pick 1–2 sounds | `trip_prep_media --country LK` | Review photos in the media review page, using the existing criteria: clear, close, wild, adult |
| 7 | **Build and check:** every in-scope species in exactly one unit, every species has a text, enough approved photos and a sound where possible, endemics flagged, all JSON valid | `trip_prep_build --country LK` (also runs in the tests) | — |
| 8 | **Publish:** add the country to the `TRIPS` list with the languages its texts exist in | Code change | Try it in the app |

Shared texts make each next country cheaper: Sri Lanka writes "Bulbuls" and "Barn Swallow" once,
and India reuses them.

Languages: English and Dutch first, like the course. The other six languages can be added per
country later; until then the trip is shown only in the languages listed in `TRIPS`.

## Data and backend

- **`Trip`** model: user, country, created and archived dates, and a small JSON state (units done,
  cards seen). Later: a travel month and stops.
- **Units are read from `units.json`**, not stored per player.
- **Species quizzes run as real games** (a new `game_type='trip_prep'`) with the species list set in
  advance. Answers land in `Answer`, so the progress number, the checklist and the trouble-spot
  pages work without extra code. The family quiz runs in the app like the course quiz
  (`app/src/core/course-quiz.ts`), because "pick the group" doesn't fit the `Answer` model.
- **Background-aware texts:** the trip API returns, per group, how many of its species the player
  knows (any country) and their names, plus which `false_friend` texts apply. The app picks the
  parts to show.

## Travel month

No new eBird integration is needed. The building blocks exist:

- `CountrySpeciesFrequency` stores frequency per month, and games already have a season filter
  (`Game.season`, `jizz/services/seasonal_frequency.py`).
- `import_ebird_country_frequencies` fills it from a country's eBird bar chart (one file, downloaded
  by hand while logged in to eBird) or from Status & Trends CSVs (3,360 species files are already
  in `jizz/ebird_st_csv`).

What's missing is the data: the local database has no monthly rows at all. Per country this is one
bar chart download and one import, so it could become pipeline step 2b. It stays out of the first
release to keep the scope small.

## Later: itinerary

The player adds stops: an eBird hotspot and dates. This is where an eBird integration is needed:
the API gives a hotspot's all-time species list and observations per date, but no per-month
frequency. Options:

- query the historic observations per day of the travel month over a few years (about 150 calls per
  hotspot, cacheable);
- the hotspot's bar chart download, by hand, for a curated list of hotspots per country.

The species list becomes the birds reported at those hotspots in that month, and units are filtered
to it; the texts stay the same. Progress could also be shown per stop ("Ready for Sinharaja: 81%").
The endemics chapter's "where to find them" cards are the first place to link hotspots.

## Open questions

1. Do rare endemics count towards the main percentage, or only towards the endemics counter?
2. Should a trip open to players in the other six languages with English texts, or only once texts
   exist in their language?
3. Is Sri Lanka the right pilot?
