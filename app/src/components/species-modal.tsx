import {
  Box,
  Button, Flex,
  Image, Link,
  Dialog,
  SimpleGrid,
  VStack,
  AspectRatio,
  Text,
  HStack,
  Spinner,
  Icon,
  IconButton,
} from "@chakra-ui/react";
import {BsBoxArrowRight, BsX} from "react-icons/bs";
import AppContext, {Species} from "../core/app-context";
import React, {useContext, useEffect, useState} from "react"
import {FormattedMessage} from "react-intl"
import { PlayableVideo } from "./playable-video"
import { MediaCredits } from "./media-credits"
import { FlagMediaButton } from "./flag-media-button"
import { createPortal } from "react-dom"
import { fetchSpeciesDetail } from "../api/fetch-species-detail"
import { fetchSpeciesCover } from "../api/fetch-species-cover"

// Add global styles for nested modal z-index
// This ensures the species modal appears above parent modals (like game detail modal)
if (typeof document !== 'undefined') {
  const styleId = 'species-modal-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      /* Target Chakra UI Dialog backdrop and content */
      .species-modal-wrapper [role="dialog"],
      .species-modal-wrapper [data-part="backdrop"],
      .species-modal-wrapper [data-part="positioner"],
      .species-modal-wrapper [data-part="content"] {
        z-index: 1400 !important;
      }
      /* Ensure backdrop is below content but above parent modal */
      .species-modal-wrapper [data-part="backdrop"] {
        z-index: 1399 !important;
      }
      .species-modal-wrapper [data-part="positioner"],
      .species-modal-wrapper [data-part="content"] {
        z-index: 1401 !important;
      }
    `;
    document.head.appendChild(style);
  }
}

export function SpeciesModal({
  species,
  onClose,
  isOpen,
  showPracticeButton = false,
  onPractice,
  practiceLoading = false,
}: {
  species?: Species;
  onClose: () => void;
  isOpen: boolean;
  showPracticeButton?: boolean;
  onPractice?: (speciesId: number) => void;
  practiceLoading?: boolean;
}) {

  const {speciesLanguage} = useContext(AppContext)
  const [activeTab, setActiveTab] = useState<'images' | 'videos' | 'sounds'>('images')
  const [detail, setDetail] = useState<Species | null>(null)
  const [coverUrl, setCoverUrl] = useState<string | null | undefined>(undefined)
  const [coverStatus, setCoverStatus] = useState<string | undefined>(undefined)
  const [coverLoading, setCoverLoading] = useState(false)

  useEffect(() => {
    if (!isOpen || !species?.id) {
      setDetail(null)
      setCoverUrl(undefined)
      setCoverStatus(undefined)
      return
    }
    setCoverUrl(species.illustration_url ?? null)
    setCoverStatus(species.illustration_status)

    let cancelled = false
    fetchSpeciesDetail(species.id, speciesLanguage)
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch(() => {
        if (!cancelled) setDetail(species)
      })

    setCoverLoading(true)
    fetchSpeciesCover(species.id)
      .then((data) => {
        if (!cancelled) {
          setCoverUrl(data.illustration_url)
          setCoverStatus(data.illustration_status)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setCoverLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isOpen, species?.id, speciesLanguage, species])

  if (!species) return null

  const display = detail ?? species
  const images = display.images ?? []
  const videos = display.videos ?? []
  const sounds = display.sounds ?? []

  const displayName = display.name_translated || (speciesLanguage === 'nl' ? display.name_nl : speciesLanguage === 'la' ? display.name_latin : display.name)

  const speciesCode = display.code?.trim()
  const ebirdUrl = speciesCode ? `https://ebird.org/species/${speciesCode}` : null
  const birdsOfTheWorldUrl = speciesCode
    ? `https://birdsoftheworld.org/bow/species/${speciesCode}/cur/introduction`
    : null

  const illustrationUrl = coverUrl !== undefined ? coverUrl : display.illustration_url
  const illustrationStatus = coverStatus ?? display.illustration_status
  const illustrationPending = coverLoading || illustrationStatus === 'pending'
  const showIllustration = Boolean(illustrationUrl) || illustrationPending

  const DialogPositionerComponent = Dialog.Positioner as React.FC<any>;
  const DialogContentComponent = Dialog.Content as React.FC<any>;
  const DialogBackdropComponent = Dialog.Backdrop as React.FC<any>;
  const DialogHeaderComponent = Dialog.Header as React.FC<any>;
  const DialogBodyComponent = Dialog.Body as React.FC<any>;
  const DialogFooterComponent = Dialog.Footer as React.FC<any>;
  // Use portal to render outside parent modal's DOM tree to avoid z-index issues
  const modalContent = (
    <Box className="species-modal-wrapper">
      <Dialog.Root open={isOpen} onOpenChange={(e: { open: boolean }) => !e.open && onClose()} size="xl">
        <DialogBackdropComponent/>
        <DialogPositionerComponent>
          <DialogContentComponent position="relative">
            <DialogHeaderComponent pr={10}>{displayName}</DialogHeaderComponent>
            <IconButton
              aria-label="Close"
              variant="ghost"
              size="sm"
              colorPalette="gray"
              position="absolute"
              top={2}
              right={2}
              zIndex={1}
              onClick={onClose}
            >
              <Icon as={BsX} boxSize={5} />
            </IconButton>
            <DialogBodyComponent>
                {(showIllustration || ebirdUrl || birdsOfTheWorldUrl) && (
                  <Flex
                    gap={3}
                    mb={2}
                    align="flex-start"
                    direction="row"
                  >
                    {showIllustration && (
                      <Box
                        flexShrink={0}
                        alignSelf="flex-start"
                        bg="white"
                        borderRadius="md"
                        py={1}
                        px={2}
                        w="72px"
                        h="72px"
                        display="flex"
                        justifyContent="flex-start"
                        alignItems="center"
                      >
                        {illustrationUrl ? (
                          <Image
                            src={illustrationUrl}
                            alt={displayName}
                            maxH="64px"
                            maxW="64px"
                            objectFit="contain"
                          />
                        ) : (
                          <Spinner size="sm" color="gray.400" />
                        )}
                      </Box>
                    )}

                    {(ebirdUrl || birdsOfTheWorldUrl) && (
                      <VStack align="start" gap={1} pt={0.5} fontSize="sm">
                        {ebirdUrl && (
                          <Link href={ebirdUrl} target="_blank" rel="noopener noreferrer">
                            <Flex gap={2} alignItems="center" color="primary.600" _hover={{ color: 'primary.700' }}>
                              <FormattedMessage defaultMessage="View on eBird" id="view_on_ebird" />
                              <BsBoxArrowRight />
                            </Flex>
                          </Link>
                        )}
                        {birdsOfTheWorldUrl && (
                          <Link href={birdsOfTheWorldUrl} target="_blank" rel="noopener noreferrer">
                            <Flex gap={2} alignItems="center" color="primary.600" _hover={{ color: 'primary.700' }}>
                              <FormattedMessage
                                defaultMessage="View on Birds of the World"
                                id="view_on_birds_of_the_world"
                              />
                              <BsBoxArrowRight />
                            </Flex>
                          </Link>
                        )}
                      </VStack>
                    )}
                  </Flex>
                )}

                <>
                {/* Tab Buttons */}
                <HStack gap={2} mb={3} borderBottomWidth="1px" pb={2}>
                  <Button
                    variant={activeTab === 'images' ? 'solid' : 'ghost'}
                    colorPalette={activeTab === 'images' ? 'primary' : 'gray'}
                    onClick={() => setActiveTab('images')}
                    size="sm"
                  >
                    <FormattedMessage defaultMessage={'Images'} id={'images'}/> ({images.length})
                  </Button>
                  <Button
                    variant={activeTab === 'videos' ? 'solid' : 'ghost'}
                    colorPalette={activeTab === 'videos' ? 'primary' : 'gray'}
                    onClick={() => setActiveTab('videos')}
                    size="sm"
                  >
                    <FormattedMessage defaultMessage={'Videos'} id={'videos'}/> ({videos.length})
                  </Button>
                  <Button
                    variant={activeTab === 'sounds' ? 'solid' : 'ghost'}
                    colorPalette={activeTab === 'sounds' ? 'primary' : 'gray'}
                    onClick={() => setActiveTab('sounds')}
                    size="sm"
                  >
                    <FormattedMessage defaultMessage={'Sounds'} id={'sounds'}/> ({sounds.length})
                  </Button>
                </HStack>
                
                {/* Tab Content */}
                {activeTab === 'images' && (
                  images.length > 0 ? (
                    <VStack gap={4} align="stretch">
                      {images.map((img, key) => (
                        <Box key={key}>
                          <Box 
                            width="100%" 
                            display="flex" 
                            justifyContent="center" 
                            alignItems="center"
                            bg="gray.50"
                            borderRadius="md"
                            p={2}
                          >
                            <Image 
                              src={img.url} 
                              alt={displayName}
                              maxWidth="100%"
                              maxHeight="100%"
                              borderRadius="md"
                            />
                          </Box>
                          <Flex justifyContent="space-between" alignItems="center" mt={2}>
                            <MediaCredits media={img} />
                            <FlagMediaButton media={img} />
                          </Flex>
                        </Box>
                      ))}
                    </VStack>
                  ) : (
                    <Text color="gray.500">
                      <FormattedMessage defaultMessage={'No images available'} id={'no_images'}/>
                    </Text>
                  )
                )}
                
                {activeTab === 'videos' && (
                  videos.length > 0 ? (
                    <VStack gap={4} align="stretch">
                      {videos.map((video, key) => (
                        <Box key={key}>
                          <AspectRatio ratio={16 / 9} width="100%">
                            <PlayableVideo
                              url={video.url}
                              controls
                              width="100%"
                              height="100%"
                            />
                          </AspectRatio>
                          <Flex justifyContent="space-between" alignItems="center" mt={2}>
                            <MediaCredits media={video} />
                            <FlagMediaButton media={video} />
                          </Flex>
                        </Box>
                      ))}
                    </VStack>
                  ) : (
                    <Text color="gray.500">
                      <FormattedMessage defaultMessage={'No videos available'} id={'no_videos'}/>
                    </Text>
                  )
                )}
                
                {activeTab === 'sounds' && (
                  sounds.length > 0 ? (
                    <VStack gap={4} align="stretch">
                      {sounds.map((sound, key) => (
                        <Box key={key}>
                          <Box>
                            <audio controls src={sound.url} style={{ width: '100%' }} />
                          </Box>
                          <Flex justifyContent="space-between" alignItems="center" mt={2}>
                            <MediaCredits media={sound} />
                            <FlagMediaButton media={sound} />
                          </Flex>
                        </Box>
                      ))}
                    </VStack>
                  ) : (
                    <Text color="gray.500">
                      <FormattedMessage defaultMessage={'No sounds available'} id={'no_sounds'}/>
                    </Text>
                  )
                )}
                </>
              </DialogBodyComponent>

              <DialogFooterComponent>
                <Flex gap={2} w="full" justify="flex-end">
                  {showPracticeButton && species?.id && onPractice ? (
                    <Button
                      colorPalette="primary"
                      loading={practiceLoading}
                      disabled={practiceLoading}
                      onClick={() => onPractice(species.id)}
                    >
                      <FormattedMessage id="trouble_spots_practice_species" defaultMessage="Practice" />
                    </Button>
                  ) : null}
                  <Button onClick={onClose} colorPalette="primary" variant={showPracticeButton ? 'outline' : 'solid'}>
                    <FormattedMessage id="close" defaultMessage="Close" />
                  </Button>
                </Flex>
              </DialogFooterComponent>
          </DialogContentComponent>
        </DialogPositionerComponent>
      </Dialog.Root>
    </Box>
  );

  // Render in portal if modal is open and document is available (browser environment)
  if (isOpen && typeof document !== 'undefined') {
    return createPortal(modalContent, document.body);
  }

  return null;
}