import { Box, Button, chakra, Flex, Heading, Image, Input, Link, SimpleGrid, Spinner, Text } from '@chakra-ui/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import {
  addCommonsPhoto,
  fetchCoursePhotos,
  fetchPlumageBackfill,
  fetchSpeciesPhotos,
  photoCourseSlug,
  savePhotoPick,
  savePhotoPlumage,
  startingPick,
  startPlumageBackfill,
  type CandidatePhoto,
  type CoursePhotoBird,
  type CoursePhotoLesson,
} from '../api/course-photos';
import { roleOf, withRole, type PhotoPick, type PhotoRole } from '../core/course-photo-roles';
import {
  formatWait,
  hasPlumageFilter,
  matchesPlumageFilter,
  PLUMAGE_OPTIONS,
  plumageBadge,
  type BackfillStatus,
  type BadgeKind,
  type PlumageField,
  type PlumageFields,
  type PlumageFilter,
} from '../core/photo-plumage';
import { useAuthProfile } from '../core/auth-profile-context';
import { Page } from '../shared/components/layout';

const ROLE_COLOR: Record<Exclude<PhotoRole, ''>, string> = {
  main: 'primary.400',
  card: 'secondary.500',
  quiz: 'blue.600',
  reject: 'error.500',
};

/** Who gave a plumage label: a person (checked), the AI (maybe wrong), or the photo's source. */
const BADGE_COLOR: Record<Exclude<BadgeKind, 'none'>, string> = {
  human: 'secondary.600',
  ai: 'orange.500',
  source: 'blue.600',
};

const Select = chakra('select');

const FIELD_TITLE: Record<PlumageField, string> = { sex: 'Sex', stage: 'Age', season: 'Season' };

/** Staff page: choose the main, card and quiz photos of every bird in the beginners course. */
export function CoursePhotosPage() {
  const courseSlug = photoCourseSlug();
  const weekKey = courseSlug === 'nl-beginners' ? 'course-photos-week' : `course-photos-week:${courseSlug}`;
  const { profile, ready } = useAuthProfile();
  const isStaff = !!(profile?.is_staff || profile?.is_superuser);
  const [lessons, setLessons] = useState<CoursePhotoLesson[] | null>(null);
  const [error, setError] = useState(false);
  // Bumped when a plumage backfill finishes, so the photo lists reload with the new labels.
  const [reload, setReload] = useState(0);
  const [week, setWeek] = useState(() => {
    try {
      const w = Number(localStorage.getItem(weekKey));
      return w >= 1 ? w : 1;
    } catch {
      return 1;
    }
  });

  useEffect(() => {
    if (!isStaff) return;
    fetchCoursePhotos()
      .then(setLessons)
      .catch(() => setError(true));
  }, [isStaff]);

  const chooseWeek = (w: number) => {
    setWeek(w);
    try {
      localStorage.setItem(weekKey, String(w));
    } catch {
      // only a convenience
    }
    window.scrollTo({ top: 0 });
  };

  const updateBird = (w: number, speciesId: number, pick: PhotoPick) =>
    setLessons((all) =>
      all?.map((l) =>
        l.week !== w ? l : { ...l, birds: l.birds.map((b) => (b.species_id === speciesId ? { ...b, pick } : b)) }
      ) ?? all
    );

  if (!ready) return <Centered><Spinner color="primary.500" /></Centered>;
  if (!isStaff) {
    return (
      <Centered>
        <Text>
          <FormattedMessage id="course_photos_staff_only" defaultMessage="This page is for Motmot admins." />
        </Text>
      </Centered>
    );
  }
  if (error) {
    return (
      <Centered>
        <Text>
          <FormattedMessage id="course_photos_load_error" defaultMessage="The course photos could not be loaded." />
        </Text>
      </Centered>
    );
  }
  if (!lessons) return <Centered><Spinner color="primary.500" /></Centered>;

  const allBirds = lessons.flatMap((l) => l.birds);
  const doneCount = allBirds.filter((b) => b.pick?.done).length;
  const lesson = lessons.find((l) => l.week === week) ?? lessons[0];

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="2xl">
          <FormattedMessage id="course_photos_title" defaultMessage="Select course photos" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={4} w="full">
          <Text color="primary.700" fontSize="sm">
            <FormattedMessage
              id="course_photos_intro"
              defaultMessage="Tap a photo to make it the main photo, a card photo (max. 3) or a quiz photo (6–8), or to leave it out. Changes go live in the course straight away. {done} of {total} birds done."
              values={{ done: doneCount, total: allBirds.length }}
            />
          </Text>
          <PlumageBackfillPanel onDone={() => setReload((n) => n + 1)} />
          <Flex gap={2} wrap="wrap">
            {lessons.map((l) => {
              // A lesson without birds of its own (a review lesson) has nothing to choose.
              const finished = l.birds.every((b) => b.pick?.done);
              return (
                <Button
                  key={l.week}
                  size="sm"
                  variant={l.week === lesson.week ? 'solid' : 'outline'}
                  colorPalette={finished ? 'secondary' : 'primary'}
                  onClick={() => chooseWeek(l.week)}
                >
                  {l.week}
                  {finished ? ' ✓' : ''}
                </Button>
              );
            })}
          </Flex>
          <Heading size="lg" color="primary.800">
            <FormattedMessage id="course_photos_lesson" defaultMessage="Lesson {week}: {title}" values={{ week: lesson.week, title: lesson.title }} />
          </Heading>
          {lesson.kind === 'review' && (
            <Text color="primary.700">
              <FormattedMessage
                id="course_photos_review_lesson"
                defaultMessage="This is a review lesson: its quiz uses the photos of earlier lessons. There is nothing to choose here."
              />
            </Text>
          )}
          {(lesson.reused ?? []).length > 0 && (
            <Text color="primary.700">
              <FormattedMessage
                id="course_photos_reused"
                defaultMessage="These birds use the photos chosen in their first lesson: {birds}."
                values={{ birds: (lesson.reused ?? []).map((r) => `${r.name} (${r.week})`).join(', ') }}
              />
            </Text>
          )}
          {lesson.birds.map((bird) => (
            <BirdPhotos
              key={`${lesson.week}-${bird.species_id}-${reload}`}
              api={{
                fetchPhotos: fetchSpeciesPhotos,
                addCommons: addCommonsPhoto,
                save: (speciesId, pick) => savePhotoPick(lesson.week, speciesId, pick),
                setPlumage: savePhotoPlumage,
              }}
              subtitle={
                <FormattedMessage id="course_photos_teaches" defaultMessage="Lesson teaches: {plumage}" values={{ plumage: bird.plumage || 'volwassen' }} />
              }
              bird={bird}
              onSaved={(pick) => updateBird(lesson.week, bird.species_id, pick)}
            />
          ))}
        </Flex>
      </Page.Body>
    </Page>
  );
}

/** Start the plumage backfill of this course's photos, with its status and the wait until the next run. */
function PlumageBackfillPanel({ onDone }: { onDone: () => void }) {
  const [status, setStatus] = useState<BackfillStatus | null>(null);
  const [approved, setApproved] = useState(true);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [retryAt, setRetryAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const wasRunning = useRef(false);

  const apply = useCallback(
    (next: BackfillStatus) => {
      setStatus(next);
      setRetryAt(Date.now() + next.retry_after * 1000);
      if (wasRunning.current && next.state !== 'running') onDone();
      wasRunning.current = next.state === 'running';
    },
    [onDone]
  );

  useEffect(() => {
    fetchPlumageBackfill().then(apply).catch(() => setFailed(true));
  }, [apply]);

  // While a run is going, look at it every few seconds; while waiting, tick the countdown.
  useEffect(() => {
    const running = status?.state === 'running';
    const waiting = retryAt > Date.now();
    if (!running && !waiting) return;
    const id = window.setInterval(() => {
      setNow(Date.now());
      if (running) fetchPlumageBackfill().then(apply).catch(() => undefined);
    }, running ? 4000 : 15000);
    return () => window.clearInterval(id);
  }, [status?.state, retryAt, apply]);

  const start = async (dry_run: boolean) => {
    setBusy(true);
    setFailed(false);
    try {
      apply(await startPlumageBackfill({ approved, dry_run }));
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  if (!status) return failed ? <Text fontSize="sm" color="error.500">The plumage backfill status could not be loaded.</Text> : null;
  const running = status.state === 'running';
  const wait = Math.max(0, Math.round((retryAt - now) / 1000));
  return (
    <Box bg="white" borderRadius="xl" borderWidth="1px" borderColor="primary.200" p={3}>
      <Flex gap={3} align="center" wrap="wrap">
        <Box flex={1} minW="220px">
          <Text fontSize="sm" fontWeight="800" color="primary.800">
            <FormattedMessage id="course_photos_backfill" defaultMessage="Plumage from the photo sources" />
          </Text>
          <Text fontSize="xs" color="primary.700">
            <FormattedMessage
              id="course_photos_backfill_help"
              defaultMessage="Looks up sex, age and season at iNaturalist, GBIF and Wikimedia Commons for the photos of this course. Never changes labels a person confirmed."
            />
          </Text>
        </Box>
        <label style={{ fontSize: '0.8rem', display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} disabled={running} />
          <FormattedMessage id="course_photos_backfill_approved" defaultMessage="Approved photos only" />
        </label>
        <Button size="sm" variant="outline" colorPalette="primary" onClick={() => void start(true)} disabled={running || busy}>
          <FormattedMessage id="course_photos_backfill_dry" defaultMessage="Dry run" />
        </Button>
        <Button size="sm" colorPalette="primary" onClick={() => void start(false)} loading={busy} disabled={running || wait > 0}>
          <FormattedMessage id="course_photos_backfill_run" defaultMessage="Run backfill" />
        </Button>
      </Flex>
      <Text fontSize="xs" mt={2} color={status.state === 'error' || failed ? 'error.500' : 'primary.700'}>
        {running && `Running since ${new Date((status.started_at ?? 0) * 1000).toLocaleTimeString()}${status.dry_run ? ' (dry run)' : ''}…`}
        {status.state === 'done' && `Last run by ${status.by} finished ${new Date((status.finished_at ?? 0) * 1000).toLocaleString()}${status.dry_run ? ' (dry run, nothing written)' : ''}.`}
        {status.state === 'error' && 'The last run failed.'}
        {status.state === 'idle' && 'No run yet.'}
        {!running && wait > 0 ? ` A real run can start again in ${formatWait(wait)}.` : ''}
        {status.error && status.state !== 'running' ? ` ${status.error}` : ''}
        {failed ? ' The request failed.' : ''}
      </Text>
      {(status.output ?? []).length > 0 ? (
        <Box as="pre" mt={1} fontSize="2xs" color="primary.700" whiteSpace="pre-wrap" maxH="140px" overflowY="auto">
          {(status.output ?? []).join('\n')}
        </Box>
      ) : null}
    </Box>
  );
}

export function Centered({ children }: { children: React.ReactNode }) {
  return (
    <Page>
      <Page.Body>
        <Flex justify="center" py={10}>
          {children}
        </Flex>
      </Page.Body>
    </Page>
  );
}

/** What the bird photo picker needs from its page: where photos come from and where picks go. */
export type PhotoPickApi = {
  fetchPhotos: (speciesId: number) => Promise<CandidatePhoto[]>;
  addCommons: (speciesId: number, link: string) => Promise<CandidatePhoto>;
  save: (speciesId: number, pick: PhotoPick) => Promise<PhotoPick>;
  /** Confirm or correct a photo's plumage (a human label). Without it the plumage is shown, not editable. */
  setPlumage?: (mediaId: number, fields: Partial<Record<PlumageField, string>>) => Promise<PlumageFields>;
};

export function BirdPhotos({
  api,
  bird,
  subtitle,
  onSaved,
}: {
  api: PhotoPickApi;
  bird: CoursePhotoBird;
  /** The line under the latin name; the course shows what the lesson teaches. */
  subtitle?: React.ReactNode;
  onSaved: (pick: PhotoPick) => void;
}) {
  const intl = useIntl();
  const [photos, setPhotos] = useState<CandidatePhoto[] | null>(null);
  const [pick, setPick] = useState<PhotoPick>(() => startingPick(bird));
  const [saving, setSaving] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [open, setOpen] = useState<number | null>(null);
  const [commonsLink, setCommonsLink] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');
  const [added, setAdded] = useState<CandidatePhoto[]>([]);
  const [filter, setFilter] = useState<PlumageFilter>({});
  // Only photos a reviewer approved (plus the chosen ones): the rest are often small or far away.
  const [approvedOnly, setApprovedOnly] = useState(true);
  // Labels a person confirmed or corrected here, laid over the photos as they were loaded.
  const [overrides, setOverrides] = useState<Record<number, PlumageFields>>({});
  const [plumageError, setPlumageError] = useState(false);
  // A bird that is done folds away; the owner can unfold it again.
  const [folded, setFolded] = useState(() => !!startingPick(bird).done);

  const addFromCommons = async () => {
    if (!commonsLink.trim()) return;
    setAdding(true);
    setAddError('');
    try {
      const photo = await api.addCommons(bird.species_id, commonsLink.trim());
      setPhotos((all) => (all && !all.some((p) => p.id === photo.id) ? [photo, ...all] : all));
      setAdded((list) => (list.some((p) => p.id === photo.id) ? list : [photo, ...list]));
      setCommonsLink('');
      setOpen(photo.id);
    } catch (e) {
      setAddError(e instanceof Error ? e.message : String(e));
    } finally {
      setAdding(false);
    }
  };

  useEffect(() => {
    api.fetchPhotos(bird.species_id)
      .then(setPhotos)
      .catch(() => setPhotos([]));
  }, [bird.species_id]);

  const byId = useMemo(
    () => new Map((photos ?? []).map((p) => [p.id, { ...p, ...overrides[p.id] } as CandidatePhoto])),
    [photos, overrides]
  );
  // Chosen photos first, then the rest in the order the server gave (best reviewed first).
  const ordered = useMemo(() => {
    if (!photos) return [];
    const chosen = [...pick.card, ...pick.quiz].map((id) => byId.get(id)).filter((p): p is CandidatePhoto => !!p);
    const rest = photos.filter((p) => !pick.card.includes(p.id) && !pick.quiz.includes(p.id) && !added.some((a) => a.id === p.id));
    return [...chosen, ...added.filter((a) => !chosen.some((c) => c.id === a.id)), ...rest];
    // Order is fixed when the photos load, so tiles don't jump while choosing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photos, added]);
  const shown = useMemo(
    () =>
      ordered
        .map((p) => byId.get(p.id) ?? p)
        .filter((p) => matchesPlumageFilter(p, filter))
        .filter((p) => !approvedOnly || p.approved > 0 || pick.card.includes(p.id) || pick.quiz.includes(p.id)),
    [ordered, byId, filter, approvedOnly, pick]
  );

  const setPlumage = async (mediaId: number, fields: Partial<Record<PlumageField, string>>) => {
    if (!api.setPlumage) return;
    setPlumageError(false);
    try {
      const saved = await api.setPlumage(mediaId, fields);
      setOverrides((all) => ({ ...all, [mediaId]: saved }));
    } catch {
      setPlumageError(true);
    }
  };
  const missing = photos ? [...pick.card, ...pick.quiz].filter((id) => !byId.has(id)) : [];

  const save = useCallback(
    async (next: PhotoPick) => {
      setPick(next);
      setSaving('saving');
      try {
        // Photos that are no longer visible cannot be saved; drop them.
        const visible = (ids: number[]) => ids.filter((id) => byId.has(id));
        const body = { ...next, card: visible(next.card), quiz: visible(next.quiz), reject: visible(next.reject) };
        const saved = await api.save(bird.species_id, body);
        setPick(saved);
        onSaved(saved);
        setSaving('saved');
      } catch {
        setSaving('error');
      }
    },
    [api, bird.species_id, byId, onSaved]
  );

  const main = pick.card[0] ? byId.get(pick.card[0]) : undefined;

  return (
    <Box bg="white" borderRadius="xl" borderWidth={pick.done ? '2px' : '1px'} borderColor={pick.done ? 'secondary.500' : 'primary.200'} p={4}>
      <Flex gap={3} align="flex-start" wrap="wrap">
        <Box flex={1} minW="200px">
          <Text fontSize="xl" fontWeight="800" color="primary.800">
            {bird.name}
          </Text>
          <Text fontStyle="italic" fontSize="sm" color="primary.700">
            {bird.latin}
          </Text>
          {subtitle ? (
            <Text fontSize="sm" fontWeight="700" color="primary.700" mt={1}>
              {subtitle}
            </Text>
          ) : null}
          {missing.length > 0 ? (
            <Text fontSize="sm" color="error.500" fontWeight="600">
              <FormattedMessage
                id="course_photos_missing"
                defaultMessage="{count} chosen photos are no longer visible and will be dropped."
                values={{ count: missing.length }}
              />
            </Text>
          ) : null}
        </Box>
        <Text fontSize="xs" color={saving === 'error' ? 'error.500' : 'primary.600'} alignSelf="center">
          {saving === 'saving' && intl.formatMessage({ id: 'course_photos_saving', defaultMessage: 'Saving…' })}
          {saving === 'saved' && intl.formatMessage({ id: 'course_photos_saved', defaultMessage: 'Saved' })}
          {saving === 'error' && intl.formatMessage({ id: 'course_photos_save_error', defaultMessage: 'Not saved. Try again.' })}
        </Text>
        <Button
          size="sm"
          variant={pick.done ? 'solid' : 'outline'}
          colorPalette="secondary"
          onClick={() => {
            setFolded(!pick.done);
            void save({ ...pick, done: !pick.done });
          }}
        >
          {pick.done ? '✓ ' : ''}
          <FormattedMessage id="course_photos_done" defaultMessage="Done" />
        </Button>
        <Button size="sm" variant="ghost" colorPalette="primary" onClick={() => setFolded((f) => !f)}>
          {folded ? '▸ ' : '▾ '}
          {folded
            ? intl.formatMessage({ id: 'course_photos_unfold', defaultMessage: 'Show' })
            : intl.formatMessage({ id: 'course_photos_fold', defaultMessage: 'Hide' })}
        </Button>
      </Flex>

      {!folded && (<>
      <Flex gap={4} mt={3} wrap="wrap" align="flex-start">
        <Box w={{ base: 'full', md: '280px' }} aspectRatio={4 / 3} bg="gray.800" borderRadius="lg" overflow="hidden" flexShrink={0}>
          {main ? (
            <Image src={main.url} alt="" w="full" h="full" objectFit="cover" />
          ) : (
            <Flex h="full" align="center" justify="center" color="gray.200" fontSize="sm" p={3} textAlign="center">
              <FormattedMessage id="course_photos_no_main" defaultMessage="No main photo yet" />
            </Flex>
          )}
        </Box>
        <Flex direction="column" gap={2} flex={1} minW="200px">
          <RoleRow label="Card" color={ROLE_COLOR.card} ids={pick.card} limit="3" byId={byId} onOpen={setOpen} />
          <RoleRow label="Quiz" color={ROLE_COLOR.quiz} ids={pick.quiz} limit="6–8" byId={byId} onOpen={setOpen} />
          <RoleRow label="Not used" color={ROLE_COLOR.reject} ids={pick.reject} byId={byId} onOpen={setOpen} />
        </Flex>
      </Flex>

      {photos === null ? (
        <Flex justify="center" py={6}>
          <Spinner color="primary.500" />
        </Flex>
      ) : (
        <>
          <Flex mt={4} mb={2} gap={2} align="center" wrap="wrap">
            <Text fontSize="xs" color="primary.600" flex={1} minW="120px">
              <FormattedMessage id="course_photos_count" defaultMessage="{count} visible photos" values={{ count: photos.length }} />
              {hasPlumageFilter(filter) || approvedOnly ? ` · ${shown.length} shown` : ''}
            </Text>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
              <input type="checkbox" checked={approvedOnly} onChange={(e) => setApprovedOnly(e.target.checked)} />
              <FormattedMessage id="course_photos_approved_only" defaultMessage="Approved only" />
            </label>
            <Input
              size="sm"
              maxW="420px"
              value={commonsLink}
              onChange={(e) => setCommonsLink(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void addFromCommons();
              }}
              placeholder={intl.formatMessage({ id: 'course_photos_commons_placeholder', defaultMessage: 'Link to a photo on Wikimedia Commons' })}
              aria-label={intl.formatMessage({ id: 'course_photos_commons_placeholder', defaultMessage: 'Link to a photo on Wikimedia Commons' })}
            />
            <Button size="sm" colorPalette="primary" onClick={() => void addFromCommons()} loading={adding} disabled={!commonsLink.trim()}>
              <FormattedMessage id="course_photos_commons_add" defaultMessage="Add photo" />
            </Button>
          </Flex>
          {addError ? (
            <Text fontSize="sm" color="error.500" mb={2}>
              {addError}
            </Text>
          ) : null}
          <PlumageFilterRow filter={filter} onChange={setFilter} />
          <SimpleGrid minChildWidth="120px" gap={2}>
            {shown.map((p) => {
              const role = roleOf(pick, p.id);
              return (
                <Box
                  as="button"
                  key={p.id}
                  position="relative"
                  aspectRatio={4 / 3}
                  borderRadius="md"
                  overflow="hidden"
                  borderWidth="3px"
                  borderColor={role ? ROLE_COLOR[role] : 'transparent'}
                  bg="gray.800"
                  onClick={() => setOpen(p.id)}
                  aria-label={`${bird.name} ${p.id}`}
                >
                  <Image src={p.thumb} alt="" loading="lazy" w="full" h="full" objectFit="cover" opacity={role === 'reject' ? 0.35 : 1} />
                  {role ? (
                    <Text position="absolute" top={1} left={1} fontSize="2xs" fontWeight="800" color="white" bg={ROLE_COLOR[role]} px={1.5} borderRadius="sm">
                      {role === 'main' ? 'MAIN' : role === 'card' ? 'CARD' : role === 'quiz' ? 'QUIZ' : '✗'}
                    </Text>
                  ) : null}
                  {plumageBadge(p).kind !== 'none' ? (
                    <Text
                      position="absolute"
                      bottom={1}
                      left={1}
                      fontSize="2xs"
                      fontWeight="800"
                      color="white"
                      bg={BADGE_COLOR[plumageBadge(p).kind as Exclude<BadgeKind, 'none'>]}
                      px={1}
                      borderRadius="sm"
                      title={plumageBadge(p).title}
                    >
                      {plumageBadge(p).kind === 'human' ? '✓ ' : ''}
                      {plumageBadge(p).text}
                    </Text>
                  ) : null}
                  {p.approved || p.rejected ? (
                    <Text position="absolute" bottom={1} right={1} fontSize="2xs" fontWeight="700" color="white" bg="blackAlpha.700" px={1} borderRadius="sm">
                      {p.approved ? `✓${p.approved}` : ''}
                      {p.rejected ? ` ✗${p.rejected}` : ''}
                    </Text>
                  ) : null}
                </Box>
              );
            })}
          </SimpleGrid>
        </>
      )}
      </>)}

      {open !== null && byId.get(open) ? (
        <PhotoSheet
          photo={byId.get(open)!}
          role={roleOf(pick, open)}
          onRole={(role) => save(withRole(pick, open, role))}
          onPlumage={api.setPlumage ? (fields) => setPlumage(open, fields) : undefined}
          plumageError={plumageError}
          onPrev={() => {
            const i = shown.findIndex((p) => p.id === open);
            if (i > 0) setOpen(shown[i - 1].id);
          }}
          onNext={() => {
            const i = shown.findIndex((p) => p.id === open);
            if (i >= 0 && i < shown.length - 1) setOpen(shown[i + 1].id);
          }}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </Box>
  );
}

function PlumageFilterRow({ filter, onChange }: { filter: PlumageFilter; onChange: (f: PlumageFilter) => void }) {
  return (
    <Flex gap={2} align="center" wrap="wrap" mb={2}>
      <Text fontSize="xs" fontWeight="800" textTransform="uppercase" color="primary.700">
        <FormattedMessage id="course_photos_plumage_filter" defaultMessage="Plumage" />
      </Text>
      {(Object.keys(PLUMAGE_OPTIONS) as PlumageField[]).map((field) => (
        <PlumageSelect
          key={field}
          field={field}
          value={filter[field] ?? ''}
          anyLabel={`${FIELD_TITLE[field]}: all`}
          noneLabel="not labelled"
          onChange={(value) => onChange({ ...filter, [field]: value })}
        />
      ))}
      {hasPlumageFilter(filter) ? (
        <Button size="xs" variant="ghost" onClick={() => onChange({})}>
          <FormattedMessage id="course_photos_plumage_clear" defaultMessage="Clear" />
        </Button>
      ) : null}
    </Flex>
  );
}

function PlumageSelect({
  field,
  value,
  anyLabel,
  noneLabel,
  onChange,
}: {
  field: PlumageField;
  value: string;
  anyLabel: string;
  /** Adds a "not labelled" choice (for the filter); the editor has an empty choice instead. */
  noneLabel?: string;
  onChange: (value: string) => void;
}) {
  return (
    <Select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={FIELD_TITLE[field]}
      fontSize="sm"
      borderWidth="1px"
      borderColor="primary.200"
      borderRadius="md"
      px={2}
      py={1}
      bg="white"
    >
      <option value="">{anyLabel}</option>
      {PLUMAGE_OPTIONS[field].map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
      {noneLabel ? <option value="none">{noneLabel}</option> : null}
    </Select>
  );
}

function RoleRow({
  label,
  color,
  ids,
  limit,
  byId,
  onOpen,
}: {
  label: string;
  color: string;
  ids: number[];
  limit?: string;
  byId: Map<number, CandidatePhoto>;
  onOpen: (id: number) => void;
}) {
  return (
    <Flex gap={2} align="center" wrap="wrap">
      <Box w="90px" flexShrink={0}>
        <Text fontSize="xs" fontWeight="800" textTransform="uppercase" color={color}>
          {label}
        </Text>
        {limit ? (
          <Text fontSize="xs" color="primary.600">
            {ids.length} / {limit}
          </Text>
        ) : null}
      </Box>
      {ids.length === 0 ? <Text fontSize="sm" color="primary.600">–</Text> : null}
      {ids.map((id) => {
        const p = byId.get(id);
        return p ? (
          <Box as="button" key={id} onClick={() => onOpen(id)} w="72px" h="54px" borderRadius="md" overflow="hidden" borderWidth="2px" borderColor={color} flexShrink={0}>
            <Image src={p.thumb} alt="" w="full" h="full" objectFit="cover" />
          </Box>
        ) : (
          <Box key={id} w="72px" h="54px" borderRadius="md" borderWidth="2px" borderStyle="dashed" borderColor="error.500" title={`${id}`} />
        );
      })}
    </Flex>
  );
}

function PhotoSheet({
  photo,
  role,
  onRole,
  onPlumage,
  plumageError,
  onPrev,
  onNext,
  onClose,
}: {
  photo: CandidatePhoto;
  role: PhotoRole;
  onRole: (role: PhotoRole) => void;
  /** Confirm (no fields) or correct the plumage; missing when the page cannot edit it. */
  onPlumage?: (fields: Partial<Record<PlumageField, string>>) => void;
  plumageError?: boolean;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft') onPrev();
      if (e.key === 'ArrowRight') onNext();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, onPrev, onNext]);

  const roles: { role: PhotoRole; label: string; color: string }[] = [
    { role: 'main', label: 'Main photo', color: ROLE_COLOR.main },
    { role: 'card', label: 'Card photo', color: ROLE_COLOR.card },
    { role: 'quiz', label: 'Quiz photo', color: ROLE_COLOR.quiz },
    { role: 'reject', label: 'Don’t use', color: ROLE_COLOR.reject },
  ];

  return (
    <Box position="fixed" inset={0} bg="blackAlpha.700" zIndex={1400} display="flex" alignItems="center" justifyContent="center" p={3} onClick={onClose}>
      <Box bg="white" borderRadius="xl" p={4} w="min(720px, 100%)" maxH="95vh" overflowY="auto" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <Image src={photo.url} alt="" w="full" maxH="60vh" objectFit="contain" bg="gray.900" borderRadius="lg" />
        <Text fontSize="xs" color="primary.700" mt={2}>
          #{photo.id} · {photo.source}
          {photo.contributor ? ` · ${photo.contributor}` : ''}
          {photo.license ? ` · ${photo.license}` : ''} · ✓{photo.approved} ✗{photo.rejected}
          {photo.link ? (
            <>
              {' · '}
              <Link href={photo.link} target="_blank" rel="noopener noreferrer" color="blue.600">
                <FormattedMessage id="course_photos_source" defaultMessage="source" />
              </Link>
            </>
          ) : null}
        </Text>
        <PlumageEditor photo={photo} onPlumage={onPlumage} error={plumageError} />
        <SimpleGrid columns={2} gap={2} mt={3}>
          {roles.map((r) => (
            <Button
              key={r.role}
              variant={role === r.role ? 'solid' : 'outline'}
              borderColor={r.color}
              bg={role === r.role ? r.color : undefined}
              color={role === r.role ? 'white' : 'primary.800'}
              onClick={() => onRole(r.role)}
            >
              {r.label}
            </Button>
          ))}
        </SimpleGrid>
        <Flex gap={2} mt={2}>
          <Button flex={1} variant="ghost" onClick={() => onRole('')}>
            No role
          </Button>
          <Button variant="outline" onClick={onPrev}>
            ←
          </Button>
          <Button variant="outline" onClick={onNext}>
            →
          </Button>
          <Button variant="outline" onClick={onClose}>
            ✕
          </Button>
        </Flex>
      </Box>
    </Box>
  );
}

/** The plumage labels of the open photo, who gave them, and the controls to confirm or correct them. */
function PlumageEditor({
  photo,
  onPlumage,
  error,
}: {
  photo: CandidatePhoto;
  onPlumage?: (fields: Partial<Record<PlumageField, string>>) => void;
  error?: boolean;
}) {
  const badge = plumageBadge(photo);
  const human = photo.plumage_source === 'human';
  return (
    <Box mt={3} p={3} borderWidth="1px" borderColor="primary.200" borderRadius="lg">
      <Flex gap={2} align="center" wrap="wrap">
        <Text fontSize="xs" fontWeight="800" textTransform="uppercase" color="primary.700">
          <FormattedMessage id="course_photos_plumage" defaultMessage="Plumage" />
        </Text>
        {badge.kind === 'none' ? (
          <Text fontSize="sm" color="primary.600">
            <FormattedMessage id="course_photos_plumage_none" defaultMessage="not labelled" />
          </Text>
        ) : (
          <Text fontSize="xs" fontWeight="800" color="white" bg={BADGE_COLOR[badge.kind]} px={1.5} borderRadius="sm" title={badge.title}>
            {human ? '✓ ' : ''}
            {badge.title}
          </Text>
        )}
        {onPlumage && badge.kind !== 'none' && !human ? (
          <Button size="xs" colorPalette="secondary" onClick={() => onPlumage({})}>
            <FormattedMessage id="course_photos_plumage_confirm" defaultMessage="Confirm" />
          </Button>
        ) : null}
      </Flex>
      {onPlumage ? (
        <Flex gap={2} mt={2} wrap="wrap">
          {(Object.keys(PLUMAGE_OPTIONS) as PlumageField[]).map((field) => (
            <PlumageSelect
              key={field}
              field={field}
              value={photo[field] ?? ''}
              anyLabel={`${FIELD_TITLE[field]}: unknown`}
              onChange={(value) => onPlumage({ [field]: value })}
            />
          ))}
        </Flex>
      ) : null}
      {error ? (
        <Text fontSize="sm" color="error.500" mt={1}>
          <FormattedMessage id="course_photos_plumage_error" defaultMessage="The plumage could not be saved." />
        </Text>
      ) : null}
    </Box>
  );
}

export default CoursePhotosPage;
