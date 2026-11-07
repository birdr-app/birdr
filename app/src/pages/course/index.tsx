import { Box, Button, Flex, Heading, Image, Spinner, Text } from '@chakra-ui/react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { currentWeek, fetchCourse, isLessonOpen, loadProgress, type Course } from '../../api/course';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { Page } from '../../shared/components/layout';

/** The beginners course: all lessons as a path, the next one open. Dutch only. */
export function CoursePage() {
  const navigate = useNavigate();
  const [course, setCourse] = useState<Course | null>(null);
  const [error, setError] = useState(false);
  const progress = loadProgress();

  const load = useCallback(() => {
    setError(false);
    fetchCourse()
      .then(setCourse)
      .catch(() => setError(true));
  }, []);
  useEffect(load, [load]);

  if (error || !course) {
    return (
      <Page>
        <Page.Body>
          <Flex direction="column" align="center" gap={3} py={10}>
            {error ? (
              <>
                <Text>De cursus kon niet worden geladen.</Text>
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

  const done = course.lessons.filter((l) => progress.completed[String(l.week)]).length;
  const week = currentWeek(course.lessons, progress);
  const next = course.lessons.find((l) => l.week === week);
  const allDone = done === course.lessons.length;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="2xl">
          {course.title}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full">
          <Flex align="center" gap={3} bg="secondary.700" borderRadius="xl" p={4}>
            <BirdrArtImage filename="birdr-success.png" alt="" width="80px" height="80px" objectFit="contain" bg="transparent" flexShrink={0} />
            <Box flex={1} minW={0}>
              <Text color="white" fontSize="md">
                {course.subtitle}
              </Text>
              <Box h="6px" bg="whiteAlpha.300" borderRadius="full" mt={3} overflow="hidden">
                <Box h="6px" bg="primary.300" w={`${Math.max(3, (done / course.lessons.length) * 100)}%`} />
              </Box>
              <Text color="secondary.100" fontSize="sm" mt={1}>
                {done} van {course.lessons.length} lessen klaar
              </Text>
            </Box>
          </Flex>

          {next && !allDone ? (
            <Box bg="white" borderRadius="xl" p={4} borderWidth="2px" borderColor="primary.200">
              <Text fontSize="xs" fontWeight="700" textTransform="uppercase" letterSpacing="0.06em" color="primary.500">
                {done === 0 ? 'Begin hier' : 'Volgende les'}
              </Text>
              <Text fontSize="xl" fontWeight="700" color="primary.800">
                Les {next.week}: {next.title}
              </Text>
              <Text fontSize="sm" color="primary.700" mb={3}>
                {next.bird_count > 0 ? `${next.bird_count} vogels · ` : ''}
                {next.minutes} minuten
              </Text>
              <Button colorPalette="primary" w="full" onClick={() => navigate(`/course/${next.week}`)}>
                {done === 0 ? 'Start de eerste les' : 'Start les'}
              </Button>
            </Box>
          ) : (
            <Box bg="white" borderRadius="xl" p={4} borderWidth="2px" borderColor="primary.200">
              <Text fontSize="xl" fontWeight="700" color="primary.800">
                Je hebt de hele cursus gedaan!
              </Text>
              <Text fontSize="sm" color="primary.700">
                Herhaal een les wanneer je wilt.
              </Text>
            </Box>
          )}

          <Text fontSize="lg" fontWeight="700" color="primary.800" mt={2}>
            Alle lessen
          </Text>
          <Text fontSize="sm" color="primary.700">
            Doe elke week één les. Een les gaat open als je de vorige hebt gedaan.
          </Text>
          {course.lessons.map((lesson) => {
            const result = progress.completed[String(lesson.week)];
            const open = isLessonOpen(lesson.week, progress);
            return (
              <Button
                key={lesson.week}
                variant="outline"
                height="auto"
                py={2}
                px={3}
                justifyContent="flex-start"
                whiteSpace="normal"
                bg="white"
                borderWidth={lesson.week === week && !allDone ? '2px' : '1px'}
                borderColor={lesson.week === week && !allDone ? 'secondary.500' : 'primary.200'}
                borderRadius="lg"
                disabled={!open}
                onClick={() => navigate(`/course/${lesson.week}`)}
              >
                <Flex align="center" gap={3} w="full" textAlign="left">
                  <Flex
                    w="30px"
                    h="30px"
                    borderRadius="full"
                    align="center"
                    justify="center"
                    flexShrink={0}
                    bg={result ? 'secondary.500' : 'primary.100'}
                    color={result ? 'white' : 'primary.800'}
                    fontWeight="800"
                    fontSize="sm"
                  >
                    {result ? '✓' : lesson.week}
                  </Flex>
                  {lesson.image ? (
                    <Image src={lesson.image} alt="" w="46px" h="46px" objectFit="cover" borderRadius="md" flexShrink={0} />
                  ) : (
                    <Box w="46px" h="46px" borderRadius="md" bg="primary.100" flexShrink={0} />
                  )}
                  <Box flex={1} minW={0}>
                    <Text fontWeight="600" color="primary.800" lineClamp={2}>
                      {lesson.title}
                    </Text>
                    <Text fontSize="sm" color="primary.700" truncate>
                      {result
                        ? `Klaar · ${result.score} van ${result.total} goed`
                        : open
                          ? lesson.subtitle
                          : `Gaat open na les ${lesson.week - 1}`}
                    </Text>
                  </Box>
                </Flex>
              </Button>
            );
          })}
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default CoursePage;
