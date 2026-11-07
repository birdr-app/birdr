import { Box, Button, Flex, Heading, Image, Spinner, Text } from '@chakra-ui/react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchLesson, saveLessonResult, type CourseBird, type CourseLesson, type CourseMedia } from '../../api/course';
import { boldParts, buildCourseQuiz } from '../../core/course-quiz';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { Page } from '../../shared/components/layout';
import { BoldText, Kicker, SoundButton, StepBar } from './parts';

const SOUND_LABEL: Record<string, string> = { song: 'Zang', call: 'Roep' };

function credit(media: CourseMedia | undefined): string {
  if (!media) return '';
  const who = media.contributor?.replace(/<[^>]+>/g, '').trim();
  return [who && `Foto: ${who}`, media.license].filter(Boolean).join(' · ');
}

/** The words of the lesson that this card shows in bold, with their meaning. */
function cardWords(bird: CourseBird, lesson: CourseLesson) {
  const bold = bird.look_for.flatMap((line) => boldParts(line).filter((p) => p.bold).map((p) => p.text.toLowerCase()));
  return lesson.words.filter((w) => {
    const term = w.term.toLowerCase();
    const stem = term.slice(0, Math.max(4, term.length - 2));
    return bold.some((b) => b.startsWith(stem));
  });
}

function Photo({ media, label }: { media: CourseMedia; label?: string }) {
  return (
    <Box position="relative" borderRadius="xl" overflow="hidden" bg="primary.100" aspectRatio={4 / 3} w="full">
      <Image src={media.url} alt="" w="full" h="full" objectFit="cover" />
      {label ? (
        <Text position="absolute" left={2} bottom={2} bg="white" borderRadius="full" px={3} py={1} fontSize="sm" fontWeight="700" color="primary.800">
          {label}
        </Text>
      ) : null}
    </Box>
  );
}

/** One lesson: introduction, one screen per bird, the quiz, and the done screen. */
export function CourseLessonPage() {
  const { week: weekParam } = useParams();
  const week = Number(weekParam);
  const navigate = useNavigate();
  const [lesson, setLesson] = useState<CourseLesson | null>(null);
  const [error, setError] = useState(false);
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<{ score: number; total: number } | null>(null);

  const load = useCallback(() => {
    setError(false);
    fetchLesson(week)
      .then(setLesson)
      .catch(() => setError(true));
  }, [week]);
  useEffect(load, [load]);

  const go = (next: number) => {
    setStep(next);
    window.scrollTo({ top: 0 });
  };

  if (error || !lesson) {
    return (
      <Page>
        <Page.Body>
          <Flex direction="column" align="center" gap={3} py={10}>
            {error ? (
              <>
                <Text>De les kon niet worden geladen.</Text>
                <Button colorPalette="primary" onClick={load}>
                  Opnieuw proberen
                </Button>
              </>
            ) : (
              <Spinner color="primary.500" />
            )}
          </Flex>
        </Page.Body>
      </Page>
    );
  }

  const birds = lesson.birds;
  const quizStep = birds.length + 1;
  const doneStep = birds.length + 2;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="xl">
          Les {lesson.week}: {lesson.title}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          {step < doneStep ? <StepBar total={birds.length + 2} current={step} /> : null}
          {step === 0 ? <Intro lesson={lesson} onStart={() => go(birds.length ? 1 : quizStep)} /> : null}
          {step > 0 && step < quizStep ? (
            <BirdCard
              key={step}
              lesson={lesson}
              bird={birds[step - 1]}
              index={step - 1}
              onBack={() => go(step - 1)}
              onNext={() => go(step + 1)}
            />
          ) : null}
          {step === quizStep ? (
            <Quiz
              lesson={lesson}
              onDone={(score, total) => {
                saveLessonResult(lesson.week, score, total);
                setResult({ score, total });
                go(doneStep);
              }}
            />
          ) : null}
          {step === doneStep && result ? (
            <Done lesson={lesson} score={result.score} total={result.total} onBack={() => navigate('/course')} onRetry={() => go(quizStep)} />
          ) : null}
        </Flex>
      </Page.Body>
    </Page>
  );
}

function Intro({ lesson, onStart }: { lesson: CourseLesson; onStart: () => void }) {
  return (
    <Flex direction="column" gap={3}>
      <Kicker>Les {lesson.week} · Introductie</Kicker>
      {lesson.subtitle ? (
        <Text fontSize="lg" color="primary.700">
          {lesson.subtitle}
        </Text>
      ) : null}
      {lesson.intro.split(/\n\n+/).map((p, i) => (
        <BoldText key={i} text={p} fontSize="md" lineHeight="1.6" color="primary.800" />
      ))}
      {lesson.birds.length > 0 ? (
        <>
          <Kicker>Vandaag: {lesson.birds.length} vogels</Kicker>
          <Flex gap={2} wrap="wrap">
            {lesson.birds.map((b, i) =>
              b.images[0] ? <Image key={i} src={b.images[0].url} alt={b.name} w="64px" h="64px" objectFit="cover" borderRadius="md" /> : null
            )}
          </Flex>
        </>
      ) : null}
      <Button colorPalette="primary" size="lg" onClick={onStart} mt={2}>
        {lesson.birds.length ? 'Begin met vogel 1' : 'Begin de quiz'}
      </Button>
    </Flex>
  );
}

function BirdCard({
  lesson,
  bird,
  index,
  onBack,
  onNext,
}: {
  lesson: CourseLesson;
  bird: CourseBird;
  index: number;
  onBack: () => void;
  onNext: () => void;
}) {
  const photo = bird.images[0];
  const words = cardWords(bird, lesson);
  const compare = lesson.compare && lesson.compare.after_species_id === bird.species_id ? lesson.compare : null;
  const pair = compare
    ? compare.species_ids.map((id) => lesson.birds.find((b) => b.species_id === id)).filter((b): b is CourseBird => !!b)
    : [];
  const last = index === lesson.birds.length - 1;
  return (
    <Flex direction="column" gap={3}>
      <Kicker>
        Vogel {index + 1} van {lesson.birds.length}
      </Kicker>
      {photo ? (
        <>
          <Photo media={photo} label={bird.plumage} />
          <Text fontSize="xs" color="primary.700" mt={-2}>
            {credit(photo)}
          </Text>
        </>
      ) : null}
      <Box>
        <Text fontSize="2xl" fontWeight="700" color="primary.800">
          {bird.name}
        </Text>
        <Text fontStyle="italic" color="primary.700">
          {bird.latin}
        </Text>
      </Box>
      <Kicker>Zo herken je hem</Kicker>
      <Box as="ul" pl={5} m={0} listStyleType="disc">
        {bird.look_for.map((line, i) => (
          <Box as="li" key={i} mb={1}>
            <BoldText text={line} color="primary.800" />
          </Box>
        ))}
      </Box>
      {words.length ? (
        <Flex direction="column" gap={1} bg="secondary.50" borderRadius="lg" p={3}>
          {words.map((w) => (
            <Text key={w.term} fontSize="sm" color="primary.800">
              <Text as="span" fontWeight="700" color="secondary.600">
                {w.term}
              </Text>{' '}
              {w.explain}
            </Text>
          ))}
        </Flex>
      ) : null}
      {bird.where_when ? (
        <>
          <Kicker>Waar en wanneer</Kicker>
          <Text color="primary.800">{bird.where_when}</Text>
        </>
      ) : null}
      <Flex align="center" gap={3} bg="white" borderRadius="lg" p={3} borderWidth="1px" borderColor="primary.200">
        <SoundButton url={bird.sounds[0]?.url ?? null} label={`Luister naar de ${bird.name}`} />
        <Text fontSize="sm" color="primary.800">
          <Text as="span" fontWeight="700">
            {SOUND_LABEL[bird.sound.type] ?? 'Geluid'}{' '}
          </Text>
          {bird.sound.describe}
        </Text>
      </Flex>
      {compare && pair.length === 2 ? (
        <Flex direction="column" gap={2} bg="white" borderRadius="lg" p={3} borderWidth="2px" borderColor="secondary.300">
          <Kicker>{compare.title}</Kicker>
          <Flex gap={2}>
            {pair.map((b) => (
              <Box key={b.species_id} flex={1}>
                {b.images[0] ? <Image src={b.images[0].url} alt="" w="full" aspectRatio={1} objectFit="cover" borderRadius="md" /> : null}
                <Text fontSize="sm" fontWeight="700" color="primary.800" mt={1}>
                  {b.name}
                </Text>
              </Box>
            ))}
          </Flex>
          <Text color="primary.800">{compare.text}</Text>
        </Flex>
      ) : null}
      {bird.note ? (
        <Box bg="primary.100" borderRadius="lg" p={3}>
          <Text fontSize="sm" color="primary.800">
            {bird.note}
          </Text>
        </Box>
      ) : null}
      {bird.dont_confuse ? (
        <Box bg="primary.100" borderRadius="lg" p={3}>
          <Text fontSize="sm" color="primary.800">
            <Text as="span" fontWeight="700">
              Niet verwarren met:{' '}
            </Text>
            {bird.dont_confuse}
          </Text>
        </Box>
      ) : null}
      <Flex gap={2} mt={2}>
        <Button variant="outline" colorPalette="primary" onClick={onBack}>
          Terug
        </Button>
        <Button colorPalette="primary" flex={1} onClick={onNext}>
          {last ? 'Naar de quiz' : 'Volgende vogel'}
        </Button>
      </Flex>
    </Flex>
  );
}

function Quiz({ lesson, onDone }: { lesson: CourseLesson; onDone: (score: number, total: number) => void }) {
  const questions = useMemo(() => buildCourseQuiz(lesson), [lesson]);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);

  if (!questions.length) {
    return (
      <Flex direction="column" gap={3}>
        <Text>Voor deze les zijn nog geen quizvragen.</Text>
        <Button colorPalette="primary" onClick={() => onDone(0, 0)}>
          Les afronden
        </Button>
      </Flex>
    );
  }

  const q = questions[index];
  const answered = picked !== null;
  const right = picked === q.answer;
  const choose = (option: string) => {
    if (answered) return;
    setPicked(option);
    if (option === q.answer) setScore((s) => s + 1);
  };
  const next = () => {
    if (index + 1 < questions.length) {
      setIndex(index + 1);
      setPicked(null);
    } else {
      onDone(score, questions.length);
    }
  };

  return (
    <Flex direction="column" gap={3}>
      <Kicker>
        Quiz · vraag {index + 1} van {questions.length}
        {q.review ? ' · herhaling' : ''}
      </Kicker>
      {q.image ? <Photo key={q.image.id} media={q.image} /> : null}
      {q.sound ? (
        <Flex direction="column" align="center" gap={3} py={6} bg="white" borderRadius="xl">
          <SoundButton key={q.sound.id} url={q.sound.url} label="Luister" size={84} />
          <Text>Welke vogel hoor je?</Text>
        </Flex>
      ) : (
        <Text fontSize="lg" fontWeight="700" color="primary.800">
          Welke vogel is dit?
        </Text>
      )}
      {q.options.map((option) => {
        const isAnswer = option === q.answer;
        const isPicked = option === picked;
        const state = answered && isAnswer ? 'right' : answered && isPicked ? 'wrong' : 'none';
        return (
          <Button
            key={option}
            onClick={() => choose(option)}
            disabled={answered && !isAnswer && !isPicked}
            variant="outline"
            height="auto"
            py={3}
            justifyContent="flex-start"
            whiteSpace="normal"
            fontSize="md"
            fontWeight="600"
            color="primary.800"
            bg={state === 'right' ? 'success.50' : state === 'wrong' ? 'error.50' : 'white'}
            borderWidth="2px"
            borderColor={state === 'right' ? 'success.500' : state === 'wrong' ? 'error.500' : 'primary.200'}
          >
            {state === 'right' ? '✓ ' : state === 'wrong' ? '✗ ' : ''}
            {option}
          </Button>
        );
      })}
      {answered ? (
        <>
          <Text fontWeight="700" color={right ? 'success.500' : 'error.500'}>
            {right ? `Ja, ${q.answer}.` : `Dat was een ${q.answer}.`}
          </Text>
          <Button colorPalette="primary" onClick={next}>
            {index + 1 < questions.length ? 'Volgende vraag' : 'Bekijk je score'}
          </Button>
        </>
      ) : null}
    </Flex>
  );
}

function Done({
  lesson,
  score,
  total,
  onBack,
  onRetry,
}: {
  lesson: CourseLesson;
  score: number;
  total: number;
  onBack: () => void;
  onRetry: () => void;
}) {
  const good = total === 0 || score / total >= 0.6;
  return (
    <Flex direction="column" gap={3}>
      <Flex align="center" gap={4}>
        <BirdrArtImage
          filename={good ? 'birdr-success.png' : 'birdr-failed.png'}
          alt=""
          width="110px"
          height="110px"
          objectFit="contain"
          bg="transparent"
          flexShrink={0}
        />
        <Box>
          <Text fontSize="5xl" fontWeight="800" color="secondary.500" lineHeight="1">
            {score}/{total}
          </Text>
          <Text fontSize="2xl" fontWeight="800" color="primary.800">
            Les {lesson.week} klaar
          </Text>
        </Box>
      </Flex>
      {lesson.outside ? (
        <Box bg="white" borderRadius="lg" p={3} borderWidth="1px" borderColor="primary.200">
          <Kicker>Deze week buiten</Kicker>
          <Text color="primary.800">{lesson.outside}</Text>
        </Box>
      ) : null}
      {lesson.next ? <Text color="primary.800">{lesson.next}</Text> : null}
      <Button colorPalette="primary" onClick={onBack}>
        Terug naar de cursus
      </Button>
      <Button variant="outline" colorPalette="primary" onClick={onRetry}>
        Quiz nog een keer
      </Button>
    </Flex>
  );
}

export default CourseLessonPage;
