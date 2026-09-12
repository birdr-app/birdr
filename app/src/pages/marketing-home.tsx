import {
  Box,
  Container,
  Flex,
  Grid,
  Heading,
  Image,
  Link,
  Text,
} from '@chakra-ui/react';

const APP_STORE_URL = 'https://apps.apple.com/us/app/birdr/id6745144189';
const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=pro.birdr.app';
const APP_STORE_BADGE =
  'https://tools.applemediaservices.com/api/badges/download-on-the-app-store/black/en-us?size=250x83';
const PLAY_STORE_BADGE =
  'https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png';

const TESTIMONIALS = [
  {
    quote: 'I gave Birdr a quick spin and immediately found it incredibly useful. Kudos to the developer!',
    attribution: 'Bombay Natural History Society, India',
  },
  {
    quote: 'The bird comparisons are thorough and could really help people improve their identification skills.',
    attribution: 'Kent Ornithological Society, United Kingdom',
  },
  { quote: 'Birdr works well—even with Finnish bird names.', attribution: 'BirdLife Finland (BirdLife Suomi), Finland' },
  {
    quote: 'The Pro and Expert levels offer exactly the kind of serious identification training I was looking for.',
    attribution: 'Japan Bird Research Association, Japan',
  },
  {
    quote: 'The app looks appealing and friendly, while the higher levels provide a genuine challenge.',
    attribution: 'Japan Bird Research Association, Japan',
  },
  {
    quote: 'I really like the similar-species tests. They’re a great way to practise difficult birds.',
    attribution: 'Birdr player, South Africa',
  },
  {
    quote: 'Birdr has massively improved my bird recognition in a surprisingly short time.',
    attribution: 'Birdr player, Germany',
  },
  { quote: 'A fun and educational way to sharpen your bird-identification skills.', attribution: 'Birdr player, Netherlands' },
  {
    quote: 'The Country Challenge is great! It’s a fun way to learn the birds of different countries.',
    attribution: 'Birdr player, France',
  },
  { quote: 'A great way to study the birds you might encounter on your next trip.', attribution: 'Birdr player' },
  {
    quote: 'The confusing-pairs games make practising difficult species both focused and fun.',
    attribution: 'Birdr player, South Africa',
  },
  {
    quote: 'I’m very happy with Birdr. It’s a fantastic initiative, and it keeps getting better.',
    attribution: 'Birdr player, Netherlands',
  },
];

function StoreBadges() {
  return (
    <Flex gap={2} align="center" wrap="wrap">
      <Link href={APP_STORE_URL} target="_blank" rel="noopener noreferrer">
        <Image src={APP_STORE_BADGE} alt="Download on the App Store" height="40px" />
      </Link>
      <Link href={PLAY_STORE_URL} target="_blank" rel="noopener noreferrer">
        <Image src={PLAY_STORE_BADGE} alt="Get it on Google Play" height="58px" />
      </Link>
    </Flex>
  );
}

const cardProps = {
  bg: 'white',
  borderWidth: '1px',
  borderColor: 'primary.200',
  borderRadius: 'xl',
  p: 5,
} as const;

/** Public marketing homepage. Game chrome lives at /play. */
export function MarketingHomePage() {
  return (
    <Box bg="primary.50" minH="100vh" color="primary.800">
      <Box
        as="header"
        position="sticky"
        top={0}
        zIndex={10}
        bg="white"
        borderBottomWidth="1px"
        borderColor="primary.200"
      >
        <Container maxW="1080px" py={3} px={5}>
          <Flex justify="space-between" align="center" gap={4} wrap="wrap">
            <Link href="/" fontWeight="800" letterSpacing="0.12em" textTransform="uppercase" color="primary.600">
              Birdr
            </Link>
            <Flex gap={4} wrap="wrap" fontWeight="600" fontSize="sm" align="center">
              <Link href="/site/how-it-works/">How it works</Link>
              <Link href="/site/birds/">Species</Link>
              <Link href="/site/bird-quiz-by-country/">Countries</Link>
              <Link href="/site/community/">Community</Link>
              <Link
                href="#get-the-app"
                bg="primary.600"
                color="white"
                px={3}
                py={1.5}
                borderRadius="full"
                _hover={{ bg: 'primary.800', color: 'white' }}
              >
                Get the app
              </Link>
            </Flex>
          </Flex>
        </Container>
      </Box>

      <Container maxW="1080px" px={5} py={12}>
        <Grid templateColumns={{ base: '1fr', md: '1.15fr 0.85fr' }} gap={10} alignItems="center" mb={16}>
          <Box>
            <Text fontSize="xs" fontWeight="700" letterSpacing="0.14em" textTransform="uppercase" color="primary.500" mb={2}>
              Free bird identification training
            </Text>
            <Heading as="h1" size="4xl" lineHeight="1.1" mb={4} fontFamily="serif">
              Improve your birding skills.
            </Heading>
            <Text fontSize="xl" mb={6} maxW="38rem">
              Free photo quizzes, personalised practice and country challenges for birders worldwide.
            </Text>
            <Box id="get-the-app" scrollMarginTop="7.5rem">
              <StoreBadges />
            </Box>
            <Link href="/play" mt={3} display="inline-block" fontWeight="600">
              Or play a quiz in the browser
            </Link>
          </Box>
          <Box bg="white" borderWidth="2px" borderColor="primary.200" borderRadius="3xl" p={4} textAlign="center">
            <Image
              src="/images/birdr-start-game.png"
              alt="Birdr quiz screen with a bird illustration"
              maxW="360px"
              mx="auto"
            />
            <Text fontSize="sm" color="primary.600" mt={2}>
              Short photo quizzes. Real birds. No auto-ID.
            </Text>
          </Box>
        </Grid>

        <Heading as="h2" size="xl" mb={4}>
          What is Birdr?
        </Heading>
        <Text mb={12} maxW="46rem">
          Birdr is a free bird-identification training app. It helps birders learn to recognise species through photo, video and sound quizzes, personalised practice and country challenges. You can sign in with Google so Birdr can create your account and save your scores and learning progress.
        </Text>

        <Heading as="h2" size="xl" mb={4}>
          How Birdr teaches
        </Heading>
        <Grid templateColumns={{ base: '1fr', md: 'repeat(3, 1fr)' }} gap={4} mb={4}>
          {[
            ['1', 'See a real bird', 'Each round shows a wild photograph, not a cartoon. Pick the species from a short list.'],
            ['2', 'Learn what you missed', 'Wrong answers become practice. My Tricky Birds keeps the lookalikes that will not stick.'],
            ['3', 'Work a country list', 'Country Challenges take you from distinctive beginners to expert lookalikes.'],
          ].map(([n, title, body]) => (
            <Box key={n} {...cardProps}>
              <Flex
                w={8}
                h={8}
                align="center"
                justify="center"
                borderRadius="full"
                bg="primary.600"
                color="white"
                fontWeight="800"
                mb={3}
              >
                {n}
              </Flex>
              <Heading as="h3" size="md" mb={2}>
                {title}
              </Heading>
              <Text>{body}</Text>
            </Box>
          ))}
        </Grid>
        <Link href="/site/how-it-works/" fontWeight="600">
          See how it works
        </Link>

        <Heading as="h2" size="xl" mt={16} mb={4}>
          What you can play
        </Heading>
        <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)' }} gap={4}>
          {[
            ['Photo quizzes', 'One quick game, or a longer session. Choose a country, a level and photos, video or sound.', '/play'],
            ['Sound quizzes', 'Hear a recording and pick the species. You can also play passerine sound quizzes in the browser.', '/play'],
            ['Multiplayer', 'A live quiz for two or more players. Faster correct answers score more points.', '/play'],
            ['High scores', 'See how you rank after a quiz.', '/scores/'],
            ['My checklist', 'See which birds you named correctly in your country, and which ones you missed.', '/checklist'],
            ['Species', 'Look up a bird, see what people miss most, and open comparisons for lookalikes.', '/site/birds/'],
            ['Country Challenges', 'Structured levels for the birds of a country—from the Netherlands to Japan to Colombia.', '/site/bird-quiz-by-country/'],
            ['My Tricky Birds', 'Focused drills on the species and confusing pairs you actually mix up.', '/site/my-tricky-birds/'],
          ].map(([title, body, href]) => (
            <Box key={title} {...cardProps}>
              <Heading as="h3" size="md" mb={2}>
                {title}
              </Heading>
              <Text mb={3}>{body}</Text>
              <Link href={href} fontWeight="600">
                Learn more
              </Link>
            </Box>
          ))}
        </Grid>

        <Heading as="h2" size="xl" mt={16} mb={4}>
          What birders say
        </Heading>
        <Grid templateColumns={{ base: '1fr', md: 'repeat(3, 1fr)' }} gap={4}>
          {TESTIMONIALS.map((item) => (
            <Box key={item.quote} as="blockquote" {...cardProps}>
              <Text fontSize="lg" mb={3}>
                “{item.quote}”
              </Text>
              <Text fontSize="sm" color="primary.600" fontWeight="600">
                — {item.attribution}
              </Text>
            </Box>
          ))}
        </Grid>

        <Heading as="h2" size="xl" mt={16} mb={4}>
          Community and FAQ
        </Heading>
        <Grid templateColumns={{ base: '1fr', md: '1fr 1fr' }} gap={4}>
          <Box {...cardProps}>
            <Heading as="h3" size="md" mb={2}>
              Community
            </Heading>
            <Text mb={3}>Birdr is a small project. Send feedback or review photos if you know a country’s birds.</Text>
            <Link href="/site/community/" fontWeight="600">
              How you can help
            </Link>
          </Box>
          <Box {...cardProps}>
            <Heading as="h3" size="md" mb={2}>
              FAQ
            </Heading>
            <Text mb={3}>Is Birdr free? Does it identify birds from a photo? Where can I play?</Text>
            <Link href="/site/faq/" fontWeight="600">
              Read the FAQ
            </Link>
          </Box>
        </Grid>

        <Box bg="primary.800" color="primary.50" borderRadius="2xl" p={8} mt={16}>
          <Heading as="h2" size="xl" color="white" mb={3}>
            Get Birdr on your phone
          </Heading>
          <Text mb={4} color="primary.100">
            The apps are the best way to practise. The browser works too if you want to try a quiz first.
          </Text>
          <StoreBadges />
          <Link href="/play" mt={4} display="inline-block" color="primary.100" fontWeight="600">
            Continue in the browser
          </Link>
        </Box>
      </Container>

      <Box as="footer" bg="white" borderTopWidth="1px" borderColor="primary.200" py={10} mt={8}>
        <Container maxW="1080px" px={5}>
          <Grid templateColumns={{ base: '1fr', md: '1.4fr 1fr 1fr' }} gap={8}>
            <Box>
              <Text fontWeight="800" letterSpacing="0.12em" textTransform="uppercase" color="primary.600" mb={2}>
                Birdr
              </Text>
              <Text mb={3}>Improve your birding skills. Free on iPhone, Android and the web.</Text>
              <StoreBadges />
            </Box>
            <Box>
              <Text fontSize="xs" fontWeight="700" letterSpacing="0.08em" textTransform="uppercase" color="primary.500" mb={2}>
                Learn
              </Text>
              <Flex direction="column" gap={1}>
                <Link href="/site/how-it-works/">How it works</Link>
                <Link href="/play">Play a quiz</Link>
                <Link href="/site/birds/">Species</Link>
                <Link href="/site/my-tricky-birds/">My Tricky Birds</Link>
                <Link href="/site/bird-quiz-by-country/">Quizzes by country</Link>
              </Flex>
            </Box>
            <Box>
              <Text fontSize="xs" fontWeight="700" letterSpacing="0.08em" textTransform="uppercase" color="primary.500" mb={2}>
                Birdr
              </Text>
              <Flex direction="column" gap={1}>
                <Link href="/site/birding-app/">The app</Link>
                <Link href="/site/flocks/">Flocks</Link>
                <Link href="/site/faq/">FAQ</Link>
                <Link href="/site/community/">Community</Link>
                <Link href="/site/page/about/">About</Link>
                <Link href="/site/page/privacy/">Privacy</Link>
                <Link href="mailto:info@goedloek.nl">Contact</Link>
              </Flex>
            </Box>
          </Grid>
        </Container>
      </Box>
    </Box>
  );
}
