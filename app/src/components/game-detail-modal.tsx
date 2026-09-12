import React, { useState, useEffect, useContext } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Spinner,
  Alert,
  AlertIndicator,
  Badge,
  Dialog,
  Button,
  Image,
  Link,
  AspectRatio,
} from "@chakra-ui/react";
import { FormattedMessage } from "react-intl";
import { useNavigate } from "react-router-dom";
import { gamesService, GameDetailWithAnswers, QuestionWithAnswer } from "../api/services/games.service";
import { startSpeciesPractice } from "../api/practice";
import { format } from "date-fns";
import { PlayableVideo } from "./playable-video";
import AppContext, { Species } from "../core/app-context";
import { getCountryDisplayName } from "../data/country-names-nl";
import { SpeciesButton } from "./species-button";
import { MediaCredits } from "./media-credits";
import { playPreviewSrc } from "../utils/play-image-url";

const {
  Root: DialogRoot,
  Backdrop: DialogBackdrop,
  Positioner: DialogPositioner,
  Content: DialogContent,
  Header: DialogHeader,
  Body: DialogBody,
  Footer: DialogFooter,
  CloseTrigger: DialogCloseTrigger,
} = Dialog;

type GameDetailModalProps = {
  isOpen: boolean;
  onClose: () => void;
  gameToken: string | null;
  /** Guest MPG: fetch via /api/games/.../with-answers/?player_token= */
  playerToken?: string;
};

export const GameDetailModal = ({ isOpen, onClose, gameToken, playerToken }: GameDetailModalProps) => {
  const navigate = useNavigate();
  const { appLanguage, loadGame, loadPlayer, setGame } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const [game, setGameDetail] = useState<GameDetailWithAnswers | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedQuestionId, setExpandedQuestionId] = useState<number | null>(null);
  const [practiceSpeciesId, setPracticeSpeciesId] = useState<number | null>(null);

  useEffect(() => {
    const loadGame = async () => {
      if (!gameToken || !isOpen) {
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const data = await gamesService.getGameDetail(
          gameToken,
          playerToken ? { playerToken } : undefined
        );
        setGameDetail(data);
      } catch (err: any) {
        setError(err.message || "Failed to load game");
      } finally {
        setLoading(false);
      }
    };

    loadGame();
  }, [gameToken, isOpen, playerToken]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setGameDetail(null);
      setError(null);
      setExpandedQuestionId(null);
      setPracticeSpeciesId(null);
    }
  }, [isOpen]);

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'PPp');
    } catch {
      return dateString;
    }
  };

  const formatTime = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return '-';
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs.toFixed(0)}s`;
  };

  const getLevelLabel = (level: string) => {
    const levels: { [key: string]: string } = {
      beginner: 'Beginner',
      advanced: 'Advanced',
      expert: 'Expert',
    };
    return levels[level] || level;
  };

  const getMediaLabel = (media: string) => {
    const mediaTypes: { [key: string]: string } = {
      images: 'Images',
      audio: 'Sounds',
      video: 'Videos',
    };
    return mediaTypes[media] || media;
  };

  // Get species name in game language
  const getSpeciesName = (species: QuestionWithAnswer['species']) => {
    if (species.name_translated) {
      return species.name_translated;
    }
    if (game?.language === 'nl' && species.name_nl) {
      return species.name_nl;
    }
    if (game?.language === 'la' && species.name_latin) {
      return species.name_latin;
    }
    return species.name;
  };

  const handleQuestionClick = (question: QuestionWithAnswer) => {
    // Toggle media expansion for this question
    if (expandedQuestionId === question.id) {
      setExpandedQuestionId(null);
    } else {
      setExpandedQuestionId(question.id);
    }
  };

  const handlePracticeSpecies = async (speciesId: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!game?.country?.code) return;
    setPracticeSpeciesId(speciesId);
    setError(null);
    try {
      const result = await startSpeciesPractice(speciesId, game.country.code);
      localStorage.setItem('player-token', result.player_token);
      localStorage.setItem('game-token', result.game.token);
      await loadPlayer(result.player_token);
      const playGame = await loadGame(result.game.token);
      if (playGame) {
        setGame(playGame);
        onClose();
        navigate('/game/play');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start practice');
    } finally {
      setPracticeSpeciesId(null);
    }
  };

  // Convert question species data to Species type
  const convertToSpecies = (speciesData: QuestionWithAnswer['species']): Species => {
    return {
      id: speciesData.id,
      code: speciesData.code,
      name: speciesData.name || '',
      name_nl: speciesData.name_nl || '',
      name_latin: speciesData.name_latin || '',
      name_translated: speciesData.name_translated || speciesData.name || '',
      tax_order: '',
      tax_family: '',
      tax_family_en: '',
      images: speciesData.images || [],
      sounds: speciesData.sounds || [],
      videos: speciesData.videos || [],
    };
  };

  // Convert user answer to Species type (for incorrect answers)
  const convertAnswerToSpecies = (answer: QuestionWithAnswer['user_answer']): Species | undefined => {
    if (!answer) return undefined;
    return {
      id: answer.id,
      code: answer.code || '',
      name: answer.name || '',
      name_nl: answer.name_nl || '',
      name_latin: answer.name_latin || '',
      name_translated: answer.name || '',
      tax_order: '',
      tax_family: '',
      tax_family_en: '',
      images: answer.images || [],
      sounds: answer.sounds || [],
      videos: answer.videos || [],
    };
  };


  return (
    <>
      <DialogRoot open={isOpen} onOpenChange={(e: { open: boolean }) => !e.open && onClose()} size="xl">
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent>
            <DialogHeader>
                <FormattedMessage id="game_details" defaultMessage="Game Details" />
            </DialogHeader>
            <DialogCloseTrigger />
            <DialogBody>
                <Box maxH="70vh" overflowY="auto">
              {loading ? (
                <VStack gap={4} py={8}>
                  <Spinner size="xl" colorPalette="primary" />
                  <Text><FormattedMessage id="loading game details" defaultMessage="Loading game details..." /></Text>
                </VStack>
              ) : error ? (
                <Alert.Root status="error">
                  <AlertIndicator />
                  <Alert.Content>
                    <Alert.Title>{error}</Alert.Title>
                  </Alert.Content>
                </Alert.Root>
              ) : game ? (
                <VStack gap={6} align="stretch">
                  {/* Game Info Header */}
                  <Box p={4} borderWidth="1px" borderRadius="md" bg="gray.50">
                    <VStack align="stretch" gap={3}>
                      <HStack justify="space-between" align="start">
                        <VStack align="start" gap={1}>
                          <Heading size="md">{game.country ? getCountryDisplayName(game.country, locale) : 'Unknown Country'}</Heading>
                          <Text fontSize="sm" color="gray.600">
                            {formatDate(game.created)}
                          </Text>
                        </VStack>
                        <VStack align="end" gap={1}>
                          <Text fontSize="xl" fontWeight="bold" color="primary.600">
                            {game.total_score} <FormattedMessage id="points" defaultMessage="points" />
                          </Text>
                          {game.ended && (
                            <Badge colorPalette="green">
                              <FormattedMessage id="completed" defaultMessage="Completed" />
                            </Badge>
                          )}
                        </VStack>
                      </HStack>
                      <HStack gap={4} fontSize="sm" color="gray.600" flexWrap="wrap">
                        <Text>
                          <FormattedMessage id="level" defaultMessage="Level" />: {getLevelLabel(game.level)}
                        </Text>
                        <Text>•</Text>
                        <Text>
                          <FormattedMessage id="length" defaultMessage="Length" />: {game.length}
                        </Text>
                        <Text>•</Text>
                        <Text>
                          <FormattedMessage id="media" defaultMessage="Media" />: {getMediaLabel(game.media)}
                        </Text>
                      </HStack>
                    </VStack>
                  </Box>

                  {/* Questions List */}
                  <VStack gap={4} align="stretch">
                    <Heading size="md">
                      <FormattedMessage id="questions" defaultMessage="Questions" />
                    </Heading>
                    {game.questions.length === 0 ? (
                      <Text color="gray.500">
                        <FormattedMessage id="no_questions" defaultMessage="No questions found." />
                      </Text>
                    ) : (
                      game.questions.map((question: QuestionWithAnswer, index: number) => {
                        const speciesName = getSpeciesName(question.species);
                        const isExpanded = expandedQuestionId === question.id;
                        const showMedia = isExpanded && question.media_item;
                        
                        return (
                          <Box
                            key={question.id}
                            p={4}
                            borderWidth="1px"
                            borderRadius="md"
                            bg="white"
                            borderColor={question.correct === false ? "red.200" : question.correct === true ? "green.200" : "gray.200"}
                            cursor="pointer"
                            _hover={{ shadow: "md", transform: "translateY(-2px)" }}
                            transition="all 0.2s"
                            onClick={() => handleQuestionClick(question)}
                          >
                            <VStack align="stretch" gap={3}>
                              {/* Question Header */}
                              <HStack justify="space-between" align="start">
                                <VStack align="start" gap={1}>
                                  <Text fontWeight="bold" fontSize="lg" color="gray.800">
                                    {speciesName}
                                  </Text>
                                  {question.species.name_latin && (
                                    <Text fontSize="sm" color="gray.500">
                                      {question.species.name_latin}
                                    </Text>
                                  )}
                                  <Text fontSize="xs" color="gray.400">
                                    <FormattedMessage 
                                      id="question_number" 
                                      defaultMessage="Question {number}" 
                                      values={{ number: question.sequence || index + 1 }}
                                    />
                                  </Text>
                                </VStack>
                                {question.correct !== null && (
                                  <Badge 
                                    colorPalette={question.correct ? "green" : "red"}
                                    fontSize="sm"
                                    px={2}
                                    py={1}
                                  >
                                    {question.correct ? (
                                      <FormattedMessage id="correct" defaultMessage="Correct" />
                                    ) : (
                                      <FormattedMessage id="incorrect" defaultMessage="Incorrect" />
                                    )}
                                  </Badge>
                                )}
                              </HStack>

                              {/* Media Display (when expanded) */}
                              {showMedia && question.media_item && (
                                <Box mt={2} p={3} bg="gray.50" borderRadius="md">
                                  {question.media_item.type === 'image' && (
                                    <VStack align="stretch" gap={2}>
                                      <Image
                                        src={playPreviewSrc(question.media_item.url)}
                                        alt={speciesName}
                                        borderRadius="md"
                                        onError={(e) => {
                                          e.currentTarget.src = '/images/birdr-logo.png';
                                        }}
                                      />
                                      <MediaCredits media={question.media_item} />
                                    </VStack>
                                  )}
                                  
                                  {question.media_item.type === 'video' && (
                                    <VStack align="stretch" gap={2}>
                                      <AspectRatio ratio={16 / 9} width="100%">
                                        <PlayableVideo
                                          url={question.media_item.url}
                                          controls
                                          width="100%"
                                          height="100%"
                                        />
                                      </AspectRatio>
                                      <MediaCredits media={question.media_item} />
                                    </VStack>
                                  )}
                                  
                                  {question.media_item.type === 'audio' && (
                                    <VStack align="stretch" gap={2}>
                                      <Box>
                                        <audio controls src={question.media_item.url} style={{ width: '100%' }} />
                                      </Box>
                                      <MediaCredits media={question.media_item} />
                                    </VStack>
                                  )}
                                  
                                  <HStack gap={2} mt={4}>
                                    {/* Button to view all media for this species */}
                                    <SpeciesButton
                                      species={convertToSpecies(question.species)}
                                      colorPalette="primary"
                                    />
                                    {/* Button to view all media for the incorrect answer species */}
                                    {question.user_answer && question.correct === false && (
                                      <>
                                        <SpeciesButton
                                          species={convertAnswerToSpecies(question.user_answer)!}
                                          colorPalette="error"
                                          size="sm"
                                        />
                                        <Button
                                          size="sm"
                                          colorPalette="primary"
                                          variant="subtle"
                                          loading={practiceSpeciesId === question.species.id}
                                          disabled={practiceSpeciesId != null && practiceSpeciesId !== question.species.id}
                                          onClick={(e) => void handlePracticeSpecies(question.species.id, e)}
                                        >
                                          <FormattedMessage
                                            id="trouble_spots_practice_species"
                                            defaultMessage="Practice"
                                          />
                                        </Button>
                                      </>
                                    )}
                                  </HStack>


                                </Box>
                              )}

                              {/* User Answer (if incorrect) */}
                              {question.user_answer && question.correct === false && (
                                <Box p={3} bg="red.50" borderRadius="md" borderWidth="1px" borderColor="red.200">
                                  <VStack align="start" gap={2}>
                                    <VStack align="start" gap={1}>
                                      <Text fontSize="sm" fontWeight="medium" color="red.700">
                                        <FormattedMessage id="your_answer" defaultMessage="Your answer:" />
                                      </Text>
                                      <Text fontSize="md" color="red.800">
                                        {question.user_answer.name}
                                        {question.user_answer.name_latin && (
                                          <Text as="span" fontSize="sm" color="red.600" ml={2}>
                                            ({question.user_answer.name_latin})
                                          </Text>
                                        )}
                                      </Text>
                                    </VStack>
                                  </VStack>
                                </Box>
                              )}

                              {question.correct !== null && (
                                <HStack gap={2} fontSize="sm" color="gray.600" flexWrap="wrap" alignItems="center">
                                  {question.correct === true && question.points !== null && (
                                    <Text fontWeight="medium" color="green.600">
                                      <FormattedMessage
                                        id="score_pts"
                                        defaultMessage="Score: {points} pts"
                                        values={{ points: question.points }}
                                      />
                                    </Text>
                                  )}
                                  {question.correct === false && (
                                    <Text color="red.600">
                                      <FormattedMessage id="no_points" defaultMessage="0 pts" />
                                    </Text>
                                  )}
                                  {question.time_taken_seconds !== null && (
                                    <>
                                      {(question.correct === true && question.points !== null) ||
                                      question.correct === false ? (
                                        <Text aria-hidden>·</Text>
                                      ) : null}
                                      <Text>
                                        <FormattedMessage
                                          id="answered_in_seconds"
                                          defaultMessage="Answered in {time}"
                                          values={{ time: formatTime(question.time_taken_seconds) }}
                                        />
                                      </Text>
                                    </>
                                  )}
                                </HStack>
                              )}
                            </VStack>
                          </Box>
                        );
                      })
                    )}
                  </VStack>
                </VStack>
              ) : null}
                </Box>
            </DialogBody>
            <DialogFooter>
              <Button onClick={onClose} colorPalette="primary">
                <FormattedMessage id="close" defaultMessage="Close" />
              </Button>
            </DialogFooter>
          </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </>
  );
};

