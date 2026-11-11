# Trip prep: writing guide

For everyone writing Trip prep texts (people and Claude sessions). The plan is in `README.md`; the
file formats are below. Run `./manage.py trip_prep_texts --country <CC>` to see what's missing,
and `--worklist <file>` to get everything a writer needs in one JSON file.

## Who reads this

A birder who knows the birds of home (often Europe, sometimes North America) and is about to travel.
They know what a heron, a warbler or a wader is. They don't know bulbuls, malkohas or ioras. They
read on a phone, between other things.

## Voice

- Plain, warm, direct. Short sentences. Address the reader as "you" (Dutch: *je*).
- Active voice. No "it is worth noting", no "fascinating", no "a true gem", no "delve".
- Texts must not refer to the reader's home country or region ("as at home", "you know from
  Europe", "a Dutch estuary", "our Blackbird"). The app shows the same text to every reader. Facts
  about the bird's own range ("a winter visitor from Europe") are fine; say "widespread" instead.
- No em-dashes as asides. No "not X, but Y" constructions. No exclamation marks.
- Facts only when they help to find or recognise the bird. Check facts on Wikipedia or eBird;
  write in your own words. Never copy field-guide text.
- British English spelling (colour, grey). Bird names as the app shows them (`name.en`, `name.nl`).
- **Dutch** is written as Dutch, not translated English: natural word order, Dutch bird names from
  the worklist (`name.nl`), *je* not *u*. Dutch group names in lower case in running text
  ("de bulbuls", "de malkoha's").

## Bird group texts (`groups/<slug>.json`, shared by all countries)

```json
{
  "slug": "bulbuls",
  "about": {"en": "...", "nl": "..."},
  "false_friends": [
    {"if_known": ["leaf-warblers"], "text": {"en": "...", "nl": "..."}}
  ]
}
```

- `about`: 2-3 sentences, 30-60 words, for a reader who knows **no** bird of this group. What they
  look like (size, shape, colour), how they behave and where you see them. It must work for every
  country, so no country names and no species counts.
- `false_friends`: only where a reader who knows a *different* group could be misled by a similar
  name or look. `if_known` lists the slugs of those other groups (from the worklist's
  `all_groups`). One or two sentences: what's different. Examples: New World warblers for someone
  who knows leaf warblers; American robins (thrushes) for a European; Old World flycatchers vs tyrant
  flycatchers; Australasian robins. Most groups have none: leave the list empty.

## Species texts (`species/<ebird-code>.json`, shared by all countries)

```json
{
  "code": "revbul",
  "name": {"en": "Red-vented Bulbul", "nl": "Roodbuikbuulbuul"},
  "latin": "Pycnonotus cafer",
  "look_for": [
    {"en": "Dark, slightly crested head", "nl": "Donkere kop met een kleine kuif"},
    {"en": "Scaly brown body, white rump", "nl": "Geschubd bruin lijf, witte stuit"},
    {"en": "Bright red under the tail", "nl": "Felrood onder de staart"}
  ]
}
```

- Exactly three `look_for` lines, each 3-9 words, no full stop. The features that tell this bird from
  the others in its group, the most useful first. Shape and behaviour count ("Hovers over water
  before diving").
- Describe the plumage the quiz photos show: the adult, and for birds whose sexes differ, the male
  unless the female is just as often seen (then cover both in one line: "Male black; female brown,
  spotted").
- Mention a lookalike only inside a line, briefly ("Larger than Little Egret, yellow bill").
- Words for parts of a bird in **bold** the first time a line uses one (`**crest**`, `**rump**`,
  `**wattle**`), like the course.

## Country texts (`<cc>/texts.json`)

```json
{
  "country": "LK",
  "intro": {"en": "...", "nl": "..."},
  "groups": {"bulbuls": {"here": {"en": "...", "nl": "..."}}},
  "units": {"bulbuls": {"title": {"en": "...", "nl": "..."}, "intro": {"en": "...", "nl": "..."}}},
  "species": {"revbul": {"here": {"en": "...", "nl": "..."}}},
  "first_day": {"title": {"en": "...", "nl": "..."}, "intro": {"en": "...", "nl": "..."}},
  "endemics": {
    "why_here": {"en": "...", "nl": "..."},
    "where": [{"title": {"en": "...", "nl": "..."}, "text": {"en": "...", "nl": "..."}}],
    "families": [],
    "units": {"endemics-1": {"title": {"en": "...", "nl": "..."}}}
  }
}
```

- `intro`: 2-3 sentences that open the trip: the country's birding in a nutshell (habitats,
  seasons, what makes it special), and how many species the trip covers.
- `groups.<slug>.here`: 1-2 sentences about this group *in this country*: how many species, where
  and how you see them, which one you'll meet first. Every group in `units.json` gets one.
- `units.<slug>.title`: a short title a person would say ("Waders on the mudflats", "Bulbuls").
  Units that merge groups get a title that covers all of them ("Swifts, nightjars and a treeswift").
  Split groups get titles that say which part ("Herons and egrets", "Ibises, spoonbill and big
  herons"). At most 40 characters.
- `units.<slug>.intro`: 1-3 sentences that set the scene: where these birds are, what to look at
  to tell them apart. It ends before the cards; don't list every species.
- `species.<code>.here`: optional, one sentence, only when something about the bird *in this
  country* helps: a local form that looks different, a lookalike that occurs here, or where to see
  it. Most species need none.
- `first_day`: the opening unit of the 20 birds you'll see on day one.
- `endemics.why_here`: why the country has its own birds and how many (2-4 sentences).
- `endemics.where`: 2-4 cards for the regions or habitats that hold most endemics, with a well-known
  site or two in each.
- `endemics.families`: cards for families found only here (Madagascar's vangas). Empty when none.
- `endemics.units.<slug>.title`: a title per endemics unit.

## Lookalikes from home (`lookalikes/<here>__<home>.json`, shared by all countries)

A trip bird that a European birder could take for a bird from home: a split (Indian vs Great
Cormorant), a close relative (Brown vs Red-backed Shrike) or a look-alike (House Crow vs Jackdaw).
The country's `scope.json` lists its pairs; the file holds the texts and is shared, so Morocco and
Tunisia can use the same African Chaffinch pair.

```json
// scope.json
"lookalikes": [{"here": "orisky1", "home": "skylar"}]

// lookalikes/orisky1__skylar.json
{
  "here": "orisky1",
  "home": "skylar",
  "tell": [
    {"en": "**Smaller**, with a shorter tail", "nl": "**Kleiner**, met een kortere staart"},
    {"en": "**Rusty panel** in the folded wing", "nl": "**Roestbruin vlak** in de gevouwen vleugel"},
    {"en": "In flight **no white rear edge** to the wing", "nl": "In vlucht **geen witte achterrand** aan de vleugel"}
  ]
}
```

- `here` is a trip bird; `home` is a bird from Europe, in the trip or not.
- `tell`: two or three lines about the trip bird, each a difference from the home bird you can see
  in the field (or "go by place" when there is none). Same rules as `look_for`: at most 10 words,
  bold the deciding feature.
- Pick pairs that can really fool someone: same shape and size, or a split of a familiar species.
  Skip pairs that only share a name.
- `home` birds that aren't trip birds get photos with `trip_prep_media --country <CC> --home-only`.

