# Trip prep: region packs

A country's trip (`CR`) holds the birds a visitor meets on a normal trip, hand-picked to 200 to 300
species. For a big birding country that leaves most of the list out, and nobody visits the whole
country. A **region pack** adds the birds of one part of it, on top of the country's trip.

## How it works

- A pack is a trip of its own, with the id `<CC>-<REGION>` (`CR-CARIBBEAN`) and its own folder
  `jizz/trips/data/cr-caribbean/` with the same files as a country: `scope.json`, `units.json`,
  `texts.json`, `media.json`. Species texts (`species/<code>.json`) and group texts
  (`groups/<slug>.json`) stay shared with every other trip.
- A pack lists its species **by hand** in `scope.json` (`"manual": true`, `add`). The frequency cut
  does not apply, and any bird the country's own trip already has is left out, so a bird is never
  in two places. `trip_prep_build` reports a bird that is in both.
- A pack has no first day, no families card and no endemics chapter: those belong to the country's
  trip. Its `texts.json` needs an `intro` and a title and intro per unit; group `here` texts are not
  needed.
- `TRIPS` registers a pack like a country, with `'parent': 'CR'`. `/api/trips/` lists countries only
  (older apps never see a pack as a country). The country's payload carries `regions`: name, species
  count and intro of each published pack. A pack's payload has `parent` and `parent_name`.
- A trip over several countries (`BALTICS`, `IBERIA`, `BRITISHISLES`) has its own id and lists `countries`. Its packs
  list the `countries` their birds are recorded under (`IBERIA-MADEIRA` and `IBERIA-AZORES` use `PT`,
  `IBERIA-CANARIES` uses `ES`), so a pack can sit below country level.
- A pack with `'draft': True` in `TRIPS` is built and checked like the others, but left out of the
  country's `regions` and exempt from the photo check in the tests. Remove the flag once every bird
  has card photos.
- Apps show the packs on the country's trip home under *Regions*, with the progress of each, and open
  a pack with the normal trip home, units and quiz screens. Progress counts answers from any game, as
  everywhere else.

## Making a pack

1. Hand-pick the species (eBird codes) from the country's species that the country trip does not
   have: `scope.json` with `{"manual": true, "add": [...]}`.
2. `./manage.py trip_prep_units --country CR-CARIBBEAN`, then give every unit a title and intro in
   `texts.json` (pooled small groups make awkward generated titles).
3. `./manage.py trip_prep_texts --country CR-CARIBBEAN --worklist <file>` lists the missing shared
   texts (new species and groups); write them as for any country (`STYLE.md`).
4. `./manage.py trip_prep_media --country CR-CARIBBEAN --api https://motmot.club`, review photos for
   the species without three card photos, run it again.
5. `./manage.py trip_prep_build --country CR-CARIBBEAN` until it reports no errors, then add the
   pack to `TRIPS` with `'parent': 'CR'`.

## Which countries need packs

Species in the database that are native, endemic or introduced, against what the country's trip
holds (November 2026):

| Country | Native species | In the trip | Verdict |
|---|---|---|---|
| Costa Rica | 793 | 281 | Yes. Four packs of about 100 to 150: Caribbean lowlands (built first), highlands, south Pacific, north Pacific dry forest. |
| Uganda | 952 | 202 | Yes, the best next candidate. Packs: Albertine Rift forests (Bwindi, Mgahinga, Rwenzori), Kibale and Semuliki forests, savannah parks (Queen Elizabeth, Murchison, Lake Mburo), Mabamba and Entebbe wetlands, Kidepo and the dry north-east. |
| Sri Lanka | 357 | 199 | Not now. The country is small and all 34 endemics are in the trip; what is left is rare migrants and waders. A single *waders and migrants* pack could come later. |
| Seychelles | 90 | 55 | No. Nearly every resident bird is in the trip already. |
| Australia | 730 | 294 | Yes, wanted. The trip (`AU`) holds what a visitor meets on a normal trip; the continent has far more specialities. Packs: Wet Tropics and Cape York (Cairns, Daintree, Atherton), Top End (Darwin, Kakadu), Red Centre and outback (Alice Springs, Uluru, the arid inland and its grasswrens), south-west (Perth, Carnaby's and the jarrah forest), Tasmania, and south-east heath and mallee (Victoria, Kangaroo Island). Pelagic and offshore seabirds could be their own pack. Built and published (all six, texts and photos done, November 2026): `AU-WETTROPICS` (125 species), `AU-TOPEND` (124), `AU-REDCENTRE` (80), `AU-SOUTHWEST` (79), `AU-TASMANIA` (64), `AU-SOUTHEAST` (115). Twelve species with no usable photos in the library were left out; see `au-photos.md`. |
| Mexico | 1,010 | 291 | Yes, and six packs, because most Mexican birds are regional and the country has about 110 endemics. Packs follow groups of states: Baja California (`MX-BAJA`, 52 species), north and Sierra Madre Occidental (`MX-NORTH`, 37), West Mexico and the Pacific slope (`MX-WEST`, 53), central highlands and the Gulf slope (`MX-CENTRAL`, 89), Oaxaca and Chiapas (`MX-SOUTH`, 106) and the Yucatan Peninsula (`MX-YUCATAN`, 106). Built from GBIF/eBird records per state (`mx/occurrence.csv`); a bird sits in the country trip when no single region holds half of its records. Veracruz and Tamaulipas are with the central highlands, a separate Gulf pack would be only about 30 birds. |
| India | 1,195 | 277 | Yes, and eight packs, because the trip is a north India route and the rest of the country is regional: Western Himalaya (`IN-WESTHIMALAYA`, 66 species), Darjeeling and Sikkim (`IN-SIKKIM`, 38), Ladakh and the high Himalaya (`IN-LADAKH`, 30), Northeast India (`IN-NORTHEAST`, 73), Western Ghats and the south (`IN-WESTERNGHATS`, 75), central India's tiger forests (`IN-CENTRAL`, 39), Kutch, Gujarat and the Thar (`IN-DESERT`, 76) and the Andaman and Nicobar Islands (`IN-ANDAMAN`, 51). Hand-picked; `in/occurrence.csv` has only country-wide counts. Not covered, because few visitor birds are left: the east coast and Odisha (Chilika, Bhitarkanika), the Gangetic Terai and the Sundarbans, and the Eastern Ghats; about 480 India species are in no trip, mostly rare Himalayan and north-eastern skulkers, vagrants and seabirds. |
