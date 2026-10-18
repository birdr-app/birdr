import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Container,
  Button,
  Spinner,
  Alert,
  AlertIndicator,
} from "@chakra-ui/react";
import { FormattedMessage } from "react-intl";
import { useNavigate, useLocation } from "react-router-dom";
import { gamesService, PaginatedGamesResponse } from "../api/services/games.service";
import { authService } from "../api/services/auth.service";
import { Page } from "../shared/components/layout";
import { Game } from "../core/app-context";
import { GameRow } from "../components/game-row";

export const MyGamesPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState<{
    count: number;
    next: string | null;
    previous: string | null;
  } | null>(null);

  useEffect(() => {
    const loadGames = async () => {
      if (!authService.getAccessToken()) {
        navigate("/login");
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const data = await gamesService.getMyGames(currentPage);
        setGames(data.results);
        setPagination({
          count: data.count,
          next: data.next,
          previous: data.previous,
        });
      } catch (err: any) {
        setError(err.message || "Failed to load games");
        if (err.message?.includes("401") || err.message?.includes("Unauthorized")) {
          authService.clearTokens();
          navigate("/login");
        }
      } finally {
        setLoading(false);
      }
    };

    loadGames();
    // location.key: refetch when navigating to this screen again (browser must not reuse stale list).
  }, [currentPage, navigate, location.key]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };


  if (loading && games.length === 0) {
    return (
      <Page>
        <Page.Header>
          <Heading color={'gray.800'} size={'lg'} m={0}>
            <FormattedMessage id="my_games" defaultMessage="My games" />
          </Heading>
        </Page.Header>
        <Page.Body>
          <VStack gap={4}>
            <Spinner size="xl" colorPalette="primary" />
            <Text><FormattedMessage id="loading games" defaultMessage="Loading games..." /></Text>
          </VStack>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <Heading color={'gray.800'} size={'lg'} m={0}>
          <FormattedMessage id="my_games" defaultMessage="My games" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.lg" py={8}>
          {error && (
            <Alert.Root status="error" mb={4}>
              <AlertIndicator />
              <Alert.Content>
                <Alert.Title>{error}</Alert.Title>
              </Alert.Content>
            </Alert.Root>
          )}

          {games.length === 0 && !loading ? (
            <VStack gap={4} py={8}>
              <Text fontSize="lg" color="gray.500">
                <FormattedMessage 
                  id="no_games_played" 
                  defaultMessage="You haven't played any games yet." 
                />
              </Text>
              <Button 
                colorPalette="primary" 
                onClick={() => navigate('/start')}
              >
                <FormattedMessage id="start_game" defaultMessage="Start a Game" />
              </Button>
            </VStack>
          ) : (
            <VStack gap={4} align="stretch">
              {pagination && (
                <Text fontSize="sm" color="gray.500">
                  <FormattedMessage 
                    id="total_games" 
                    defaultMessage="Total: {count} games" 
                    values={{ count: pagination.count }}
                  />
                </Text>
              )}

              {games.map((game) => (
                <GameRow key={game.token} game={game} />
              ))}

              {/* Pagination */}
              {pagination && (pagination.next || pagination.previous) && (
                <HStack justify="center" gap={2} mt={4}>
                  <Button
                    variant="outline"
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={!pagination.previous}
                  >
                    <FormattedMessage id="previous" defaultMessage="Previous" />
                  </Button>
                  <Text fontSize="sm" color="gray.600">
                    <FormattedMessage 
                      id="page_info" 
                      defaultMessage="Page {current} of {total}" 
                      values={{
                        current: currentPage,
                        total: Math.ceil(pagination.count / 20),
                      }}
                    />
                  </Text>
                  <Button
                    variant="outline"
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={!pagination.next}
                  >
                    <FormattedMessage id="next" defaultMessage="Next" />
                  </Button>
                </HStack>
              )}
            </VStack>
          )}
        </Container>
      </Page.Body>
    </Page>
  );
};

export default MyGamesPage;

