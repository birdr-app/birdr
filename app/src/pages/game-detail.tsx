import React, { useState, useEffect, useContext } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Container,
  Spinner,
  Alert,
  AlertIndicator,
  Badge,
  Button,
} from "@chakra-ui/react";
import { FormattedMessage } from "react-intl";
import { useNavigate, useParams } from "react-router-dom";
import { gamesService, GameDetailWithAnswers, QuestionWithAnswer } from "../api/services/games.service";
import { authService } from "../api/services/auth.service";
import { Page } from "../shared/components/layout";
import AppContext from "../core/app-context";
import { getCountryDisplayName } from "../data/country-names-nl";
import { format } from "date-fns";
import { HiscoreRank } from "../components/hiscore-rank";

export const GameDetailPage = () => {
  const navigate = useNavigate();
  const { token } = useParams<{ token: string }>();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const [game, setGame] = useState<GameDetailWithAnswers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadGame = async () => {
      if (!authService.getAccessToken()) {
        navigate("/login");
        return;
      }

      if (!token) {
        setError("Game token is required");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const data = await gamesService.getGameDetail(token);
        setGame(data);
      } catch (err: any) {
        setError(err.message || "Failed to load game");
        if (err.message?.includes("401") || err.message?.includes("Unauthorized")) {
          authService.clearTokens();
          navigate("/login");
        }
      } finally {
        setLoading(false);
      }
    };

    loadGame();
  }, [token, navigate]);

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

  if (loading) {
    return (
      <Page>
        <Page.Header>
          <Heading color={'gray.800'} size={'lg'} m={0}>
            <FormattedMessage id="game_details" defaultMessage="Game Details" />
          </Heading>
        </Page.Header>
        <Page.Body>
          <VStack gap={4}>
            <Spinner size="xl" colorPalette="primary" />
            <Text><FormattedMessage id="loading game details" defaultMessage="Loading game details..." /></Text>
          </VStack>
        </Page.Body>
      </Page>
    );
  }

  if (error || !game) {
    return (
      <Page>
        <Page.Header>
          <Heading color={'gray.800'} size={'lg'} m={0}>
            <FormattedMessage id="game_details" defaultMessage="Game Details" />
          </Heading>
        </Page.Header>
        <Page.Body>
          <Container maxW="container.lg" py={8}>
            <Alert.Root status="error">
              <AlertIndicator />
              <Alert.Content>
                <Alert.Title>{error || "Game not found"}</Alert.Title>
              </Alert.Content>
            </Alert.Root>
            <Button mt={4} onClick={() => navigate('/my-games')} colorPalette="primary">
              <FormattedMessage id="back_to_games" defaultMessage="Back to My Games" />
            </Button>
          </Container>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <Heading color={'gray.800'} size={'lg'} m={0}>
          <FormattedMessage id="game_details" defaultMessage="Game Details" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.lg" py={8}>
          <VStack gap={6} align="stretch">
            {/* Game Info Header */}
            <Box p={4} borderWidth="1px" borderRadius="md" bg="white">
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
                    <HiscoreRank game={game} rank={game.hiscore_rank} />
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
                game.questions.map((question: QuestionWithAnswer, index: number) => (
                  <Box
                    key={question.id}
                    p={4}
                    borderWidth="1px"
                    borderRadius="md"
                    bg="white"
                    borderColor={question.correct === false ? "red.200" : question.correct === true ? "green.200" : "gray.200"}
                  >
                    <VStack align="stretch" gap={3}>
                      {/* Question Header */}
                      <HStack justify="space-between" align="start">
                        <VStack align="start" gap={1}>
                          <Text fontWeight="bold" fontSize="lg">
                            <FormattedMessage 
                              id="question_number" 
                              defaultMessage="Question {number}" 
                              values={{ number: question.sequence || index + 1 }}
                            />
                          </Text>
                          <Text fontSize="md" color="gray.700">
                            {question.species.name_translated || question.species.name}
                            {question.species.name_latin && (
                              <Text as="span" fontSize="sm" color="gray.500" ml={2}>
                                ({question.species.name_latin})
                              </Text>
                            )}
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

                      {/* User Answer (if incorrect) */}
                      {question.user_answer && question.correct === false && (
                        <Box p={3} bg="red.50" borderRadius="md" borderWidth="1px" borderColor="red.200">
                          <VStack align="start" gap={1}>
                            <Text fontSize="sm" fontWeight="medium" color="red.700">
                              <FormattedMessage id="your_answer" defaultMessage="Your answer:" />
                            </Text>
                            <Text fontSize="md" color="red.800">
                              {question.user_answer.name_translated || question.user_answer.name}
                              {question.user_answer.name_latin && (
                                <Text as="span" fontSize="sm" color="red.600" ml={2}>
                                  ({question.user_answer.name_latin})
                                </Text>
                              )}
                            </Text>
                          </VStack>
                        </Box>
                      )}

                      {/* Score + answer time (same basis as live play scoring) */}
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
                              {(question.correct === true && question.points !== null) || question.correct === false ? (
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
                ))
              )}
            </VStack>

            {/* Back Button */}
            <Button onClick={() => navigate('/my-games')} colorPalette="primary" variant="outline">
              <FormattedMessage id="back_to_games" defaultMessage="Back to My Games" />
            </Button>
          </VStack>
        </Container>
      </Page.Body>
    </Page>
  );
};

export default GameDetailPage;

