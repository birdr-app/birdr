# Advanced course: what the engine does

Course slug `nw-europe-advanced` (registered in `jizz/courses/content.py`). Website only for now:
`/site/advanced-bird-course/`, lessons at `.../lesson-<week>-<slug>/`, practice at `.../practice/`.
Texts per course are in `SITES` in `jizz/marketing/course.py`. The phone and web app screens are
not ported.

## Lesson file additions (on top of `uk-beginners`)

- `quiz.modes`: a mix of question kinds, for example `{"photo": 4, "photo_sound": 3, "sound": 1}`.
  A `photo_sound` question shows a photo and plays a recording of the same bird. A bird missing
  one kind falls back to the other. Without `modes` a quiz is all photo (or all sound with
  `quiz.kind: "sound"`), as in the beginners courses.
- Review lessons (`kind: "review"`) and the review slots of other lessons take the birds the
  learner has to repeat first (see below), then the fixed `quiz.review_from` weeks.
- Each bird's `plumage` text names the plumage taught ("adult female"). Spaced repetition tracks a
  bird in one plumage, key `"<species_id>|<plumage text>"`, so a female and a male Mallard are two
  birds.
- Photos in the payload carry `plumage: {sex, stage, season, source}` from `MediaPlumage` when it
  exists; the quiz says what the photo shows after each answer.

## Spaced repetition

- Leitner boxes, intervals in days by box: 0.5, 1, 3, 7, 14, 30, 60. A wrong answer sends the bird
  to box 0; a right answer moves it up one box only when it is due, so replaying a quiz cannot push
  birds up. `app/src/core/course-srs.ts` is the reference; the website runs an ES5 copy between
  `SRS-BEGIN` and `SRS-END` in `jizz/templates/marketing/_course_quiz_js.html`, and
  `app/src/__tests__/course-srs.test.ts` runs both on the same cases.
- State lives in the browser (`localStorage` key `course:<slug>:srs`). Signed-in learners also
  sync it with `GET/POST /api/courses/<slug>/srs/` (model `CourseBirdResult`; the most recently
  seen side wins per bird).
- `GET /api/courses/<slug>/practice-birds/?key=<id>|<plumage>&key=...` returns quiz material for
  due birds wherever in the course they were taught, plus all bird names and look-alike groups.
- The practice page asks ten questions from the birds that are due, in all three question modes.
