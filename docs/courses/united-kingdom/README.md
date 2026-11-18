# Birds of Britain: the UK beginners course

The English twin of the Dutch beginners course (see `docs/courses/netherlands/README.md` for the
idea, the lesson format and the principles; they all apply here). Twenty weekly lessons, same flow:
introduction, one card per bird, quiz at the end, a task for the week outside.

- Lesson files: `jizz/courses/data/uk-beginners/lesson-NN-*.json`, plus `lookalikes.json`.
- API: `/api/courses/uk-beginners/` and `/api/courses/uk-beginners/lessons/<week>/` (texts in English).
- Website: `/site/bird-course/` and `/site/bird-course/lesson-<week>-<slug>/`, English only.
- Photo picker for admins: `/course-photos?course=uk-beginners`.
- The phone and web app screens still use `COURSE_SLUG = 'nl-beginners'`, so the UK course is on the
  website only for now.

## Lessons

| Week | Lesson | New birds |
|---|---|---|
| 1 | Your first five | Blackbird ♂, House Sparrow ♂, Great Tit, Blue Tit, Robin |
| 2 | At the pond | Mallard ♂, Coot, Moorhen, Mute Swan, Grey Heron |
| 3 | Pigeons and crows | Woodpigeon, Feral Pigeon, Collared Dove, Magpie, Carrion Crow, Jackdaw |
| 4 | How to look at a bird | Starling, Chaffinch ♂, Dunnock, Wren |
| 5 | The other half | Female Blackbird, House Sparrow, Chaffinch, Mallard; young Mute Swan |
| 6 | Gulls made simple | Black-headed, Common, Herring, Lesser Black-backed Gull |
| 7 | Geese in winter ❄ | Canada, Greylag, Pink-footed, Barnacle, Brent Goose |
| 8 | Ducks: the males | Tufted Duck, Teal, Wigeon, Gadwall, Shoveler |
| 9 | Your first songs ☀ | Blackbird, Robin, Wren, Great Tit, Chiffchaff, Chaffinch (by ear) |
| 10 | Review | Quiz of weeks 1-9 |
| 11 | Fields and farmland ☀ | Lapwing, Oystercatcher, Skylark, Yellowhammer, Pheasant |
| 12 | Birds of prey | Buzzard, Kestrel, Sparrowhawk, Red Kite |
| 13 | In the woods | Great Spotted Woodpecker, Nuthatch, Jay, Treecreeper, Long-tailed Tit |
| 14 | Reeds and wetlands ☀ | Reed Bunting, Reed Warbler, Kingfisher, Great Crested Grebe, Little Grebe |
| 15 | Swallows and swifts ☀ | Swallow, House Martin, Sand Martin, Swift |
| 16 | Finches | Goldfinch, Greenfinch, Linnet, Siskin, Bullfinch |
| 17 | Thrushes | Song Thrush, Mistle Thrush, Fieldfare, Redwing |
| 18 | Waders | Curlew, Redshank, Dunlin, Sanderling, Turnstone |
| 19 | Coast and sea | Little Egret, Cormorant, Shelduck, Gannet |
| 20 | Final test | Quiz of weeks 1-19 |

What differs from the Dutch course: Collared Dove is dated to 1955 and Norfolk; the geese are the
British set (Pink-footed, Brent, Canada instead of White-fronted and Egyptian); Red Kite and
Kingfisher come in; the Dutch meadow birds (godwits, Bluethroat, Marsh Harrier, Spoonbill) make
way for farmland, estuary and sea birds.

## Where the photos and sounds came from

- **Shared birds (76 of the 86 cards):** the photo and recording ids of the Dutch lesson file.
  Each of those birds has `media_from: {course, week}` pointing at the Dutch lesson it borrowed from.
- **New birds:** Pink-footed Goose, Brent Goose, Yellowhammer, Pheasant, Red Kite, Kingfisher,
  Little Egret, Shelduck, Gannet and Eurasian Treecreeper. Photos were picked from reviewed or
  adult-labelled images and looked at; recordings from xeno-canto, quality A, no background species,
  UK or Ireland first. Nobody has listened to them yet.
- **Treecreeper is species 8477 (Certhia familiaris).** The Dutch course's "Boomkruiper" is species
  8481, the Short-toed Treecreeper, which is not the British bird.

## Before it goes live

1. Deploy, then on the server copy the photos the Dutch admins picked to the shared birds:
   `./manage.py copy_course_photo_picks --dry-run`, then without `--dry-run`.
2. Walk through the lessons in the photo picker (`/course-photos?course=uk-beginners`), especially the
   new birds. Gannet and Pink-footed Goose have the thinnest choice of good photos (the database holds
   mostly young Gannets); Pheasant had no reviewed photos at all, so those are unreviewed adult males.
3. Listen to the recordings of the new birds, and trim the long ones.
4. Have a British birder read the texts. The facts are checked against what I know, not against a source.

## The US

Nothing is built. The state commonness files suggest the country is far too varied for one course:
only 15 species are in the top 40 of 70% of the states (Red-winged Blackbird, Common Grackle,
American Robin, American Crow, Yellow-rumped Warbler, Starling, Blue Jay, Mourning Dove, American
Goldfinch, Brown-headed Cowbird, Song Sparrow, Barn Swallow, Canada Goose, Dark-eyed Junco, Mallard).
Proposed regions, with the share of the top-40 birds that most of a region's states have in common:

| Region | States | Birds in common |
|---|---|---|
| Northeast and Mid-Atlantic | ME NH VT MA CT RI NY NJ PA DE MD VA WV | 19/40 |
| Southeast | NC SC GA FL AL TN KY | 27/40 |
| South-central | TX OK AR LA | 27/40 |
| Great Lakes and Plains | OH MI IN IL WI MN IA MO ND SD NE KS | 21/40 |
| Rockies and Southwest | AZ NM CO UT NV WY ID MT | 22/40 |
| Pacific | CA OR WA | 20/40 |

A three-way split (Northeast, Northwest, South) leaves the "Northwest" as the Pacific coast, the
Rockies and the Plains together: 13 of 40 birds in common.
