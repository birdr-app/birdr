# SC readiness

Texts, scope, units and photos pass `./manage.py trip_prep_build --country SC` with no errors.
Published in `TRIPS` (`jizz/trips/content.py`) on 2026-11-08. The texts still deserve a human read.

## Photos

Reviewed on motmot.club on 2026-11-08 with the usual criteria (clear, close, wild, adult; doubtful IDs left
unreviewed). Every species has card photos. These have fewer than 6 approved photos, so their quiz repeats
pictures sooner:

| Species | Code | Approved | Link |
|---|---|---|---|
| Aldabra White-eye | `aldwhe1` | 1 | [review](https://motmot.club/media-review/SC?species=8110) |
| Lesser Noddy | `lesnod1` | 5 | [review](https://motmot.club/media-review/SC?species=2283) |
| Aldabra Fody | `rehfod3` | 5 | [review](https://motmot.club/media-review/SC?species=9617) |
| Seychelles Scops Owl | `sesowl1` | 3 | [review](https://motmot.club/media-review/SC?species=3023) |
| Seychelles Fody | `seyfod1` | 5 | [review](https://motmot.club/media-review/SC?species=9622) |
| Seychelles Parrot | `seypar1` | 3 | [review](https://motmot.club/media-review/SC?species=4048) |
| Tropical Shearwater | `troshe5` | 4 | [review](https://motmot.club/media-review/SC?species=2494) |
| Zebra Dove | `zebdov` | 5 | [review](https://motmot.club/media-review/SC?species=702) |

Notes:
- Aldabra White-eye has 1 approved photo: production has no other candidates.
- Tibetan Sand Plover: only breeding-plumage birds are approved; winter birds can't be told from Greater Sand Plover, so they stay unreviewed.

After more reviews, run `./manage.py trip_prep_media --country SC --api https://motmot.club`.
