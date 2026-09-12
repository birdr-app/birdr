import {
  Box,
  Button,
  Flex,
  Image,
  Link,
  Dialog,
  SimpleGrid,
  Portal,
  VStack,
  Text,
  Heading,
} from "@chakra-ui/react";
import { BsBoxArrowRight } from "react-icons/bs";
import { FormattedMessage } from "react-intl";
import { playVideoSources } from "../utils/play-video-url";
import { QuestionWithAnswer } from "../api/services/games.service";

type QuestionMediaModalProps = {
  question: QuestionWithAnswer | null;
  gameLanguage: string;
  gameMedia: string; // 'images', 'audio', or 'video'
  isOpen: boolean;
  onClose: () => void;
};

export const QuestionMediaModal = ({ question, gameLanguage, gameMedia, isOpen, onClose }: QuestionMediaModalProps) => {
  if (!question || !question.species) return null;

  const species = question.species;
  
  // Get species name in game language
  const getSpeciesName = () => {
    if (species.name_translated) {
      return species.name_translated;
    }
    if (gameLanguage === 'nl' && species.name_nl) {
      return species.name_nl;
    }
    if (gameLanguage === 'la' && species.name_latin) {
      return species.name_latin;
    }
    return species.name;
  };

  const speciesName = getSpeciesName();
  
  // Only show media that was used in the game
  const hasImages = gameMedia === 'images' && species.images && species.images.length > 0;
  const hasVideos = gameMedia === 'video' && species.videos && species.videos.length > 0;
  const hasSounds = gameMedia === 'audio' && species.sounds && species.sounds.length > 0;
  const hasMedia = hasImages || hasVideos || hasSounds;

  return (
    <Dialog.Root open={isOpen} onOpenChange={(e: { open: boolean }) => !e.open && onClose()} size="xl">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content maxH="90vh" display="flex" flexDirection="column">
            <Dialog.Header>
              {speciesName}
              {species.name_latin && (
                <Text as="span" fontSize="sm" color="gray.500" ml={2} fontWeight="normal">
                  ({species.name_latin})
                </Text>
              )}
            </Dialog.Header>
            <Dialog.CloseTrigger />
            <Dialog.Body flex="1" overflowY="auto">
              <VStack gap={4} align="stretch">
                <Link
                  href={`https://ebird.org/species/${species.code}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  textDecoration="none"
                >
                  <Flex gap={2} mb={4} alignItems="center" color="primary.600" _hover={{ color: "primary.700" }}>
                    <FormattedMessage defaultMessage="View on eBird" id="view_on_ebird" />
                    <BsBoxArrowRight />
                  </Flex>
                </Link>

                {!hasMedia && (
                  <Text color="gray.500">
                    <FormattedMessage id="no_media_available" defaultMessage="No media available for this species." />
                  </Text>
                )}

                {hasImages && (
                  <Box>
                    <Heading size="sm" mb={3}>
                      <FormattedMessage id="images" defaultMessage="Images" />
                    </Heading>
                    <SimpleGrid columns={{ base: 1, md: 2, xl: 3 }} gap={4}>
                      {(species.images || []).map((img, key) => (
                        <Image
                          key={key}
                          width="100%"
                          maxW="300px"
                          src={img.url}
                          alt={speciesName}
                          borderRadius="md"
                          objectFit="cover"
                        />
                      ))}
                    </SimpleGrid>
                  </Box>
                )}

                {hasVideos && (
                  <Box>
                    <Heading size="sm" mb={3}>
                      <FormattedMessage id="videos" defaultMessage="Videos" />
                    </Heading>
                    <VStack gap={4} align="stretch">
                      {(species.videos || []).map((video, key) => (
                        <Box key={key}>
                          <video
                            controls
                            playsInline
                            style={{ width: '100%', maxWidth: '600px', borderRadius: '8px' }}
                          >
                            {playVideoSources(video.url).map((source) => (
                              <source key={source.src} src={source.src} type={source.type} />
                            ))}
                          </video>
                          {video.link && (
                            <Link href={video.link} target="_blank" rel="noopener noreferrer" fontSize="sm" color="gray.600">
                              {video.link}
                            </Link>
                          )}
                        </Box>
                      ))}
                    </VStack>
                  </Box>
                )}

                {hasSounds && (
                  <Box>
                    <Heading size="sm" mb={3}>
                      <FormattedMessage id="sounds" defaultMessage="Sounds" />
                    </Heading>
                    <VStack gap={4} align="stretch">
                      {(species.sounds || []).map((sound, key) => (
                        <Box key={key}>
                          <audio controls src={sound.url} style={{ width: '100%' }} />
                          {sound.link && (
                            <Link href={sound.link} target="_blank" rel="noopener noreferrer" fontSize="sm" color="gray.600">
                              {sound.link}
                            </Link>
                          )}
                        </Box>
                      ))}
                    </VStack>
                  </Box>
                )}
              </VStack>
            </Dialog.Body>
            <Dialog.Footer>
              <Button onClick={onClose} colorPalette="primary">
                <FormattedMessage id="close" defaultMessage="Close" />
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
};

