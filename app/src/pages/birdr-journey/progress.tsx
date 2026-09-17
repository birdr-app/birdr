import { Box, Button, Flex, Spinner, Text, VStack } from '@chakra-ui/react';
import { useCallback, useContext, useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useParams } from 'react-router-dom';
import {
  getBirdrJourney,
  hasPlayableStep,
  levelTitle,
  startBirdrJourney,
  type BirdrJourney,
  type JourneyStep,
} from '../../api/birdrJourney';
import { authService } from '../../api/services/auth.service';
import { BirdrJourneyStepTrail } from '../../components/birdr-journey-step-trail';
import { BirdrLevelImage } from '../../components/birdr-level-image';
import AppContext from '../../core/app-context';
import { persistCountryChallengeSpeciesLanguage } from '../../core/journey-species-language';
import { useAuthProfile } from '../../core/auth-profile-context';
import { getCountryDisplayName } from '../../data/country-names-nl';
import { Page } from '../../shared/components/layout';
import { UseLanguages } from '../../user/use-languages';
import LanguageCombobox from '../../components/language-combobox';

export function BirdrJourneyProgressPage() {
  const { countryCode = '' } = useParams<{ countryCode: string }>();
  const navigate = useNavigate();
  const { appLanguage, language, applySpeciesLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const isAuthenticated = !!authService.getAccessToken();
  const { applyProfile } = useAuthProfile();
  const { languages } = UseLanguages();
  const [loading, setLoading] = useState(true);
  const [journey, setJourney] = useState<BirdrJourney | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      let data = await getBirdrJourney(countryCode);
      if (!data) {
        data = await startBirdrJourney(countryCode);
      }
      setJourney(data);
      if (data.pending_level_celebration) {
        navigate(`/journey/${countryCode}/celebration`, { replace: true });
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setJourney(null);
    } finally {
      setLoading(false);
    }
  }, [countryCode, navigate]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const handleStepPress = (_step: JourneyStep) => {
    if (!journey) return;
    navigate(`/journey/${countryCode}/step`);
  };

  const persistLanguage = (code: string) => {
    void persistCountryChallengeSpeciesLanguage({
      language: code,
      applySpeciesLanguage,
      isAuthenticated,
      applyProfile,
      journeyGameToken: journey?.current_game?.game?.token,
    });
  };

  const languageGhost = (
    <Flex justify="center" align="center" gap={1}>
      <Text fontSize="sm" fontWeight="600" color="primary.600" whiteSpace="nowrap">
        <FormattedMessage id="bird_names" defaultMessage="Bird names" />
      </Text>
      <Box minW="8rem" maxW="14rem">
        <LanguageCombobox
          languages={Array.isArray(languages) ? languages : []}
          value={language || 'en'}
          onChange={persistLanguage}
          variant="ghost"
        />
      </Box>
    </Flex>
  );

  if (loading && !journey) {
    return (
      <Page>
        <Page.Body>
          <VStack py={12}>
            <Spinner size="lg" color="primary.500" />
            <Text color="primary.600">
              <FormattedMessage id="loading" defaultMessage="Loading..." />
            </Text>
          </VStack>
        </Page.Body>
      </Page>
    );
  }

  if (error || !journey) {
    return (
      <Page>
        <Page.Body>
          <Text color="red.500" textAlign="center">
            {error ?? 'Failed to load'}
          </Text>
        </Page.Body>
      </Page>
    );
  }

  const countryName = getCountryDisplayName(journey.country, locale);
  const currentLevel = journey.current_level;
  const currentTitle = levelTitle(currentLevel, locale);

  if (journey.is_champion && currentLevel) {
    return (
      <Page>
        <Page.Header>
          <VStack gap={1} align="center">
            <Text>{countryName}</Text>
            {languageGhost}
          </VStack>
        </Page.Header>
        <Page.Body>
          <VStack gap={4} py={4}>
            <BirdrLevelImage iconUrl={currentLevel.icon_url} sequence={currentLevel.sequence} variant="current" size={200} />
            <Text fontSize="2xl" fontWeight="700" color="primary.800" textAlign="center">
              {currentTitle}
            </Text>
            <Text fontSize="md" color="primary.700" textAlign="center" lineHeight="tall">
              <FormattedMessage
                id="birdr_journey_champion_body"
                defaultMessage="You completed the full country challenge for this country."
              />
            </Text>
            <Button colorPalette="primary" width="full" onClick={() => navigate('/journey')}>
              <FormattedMessage id="birdr_journey_another_country" defaultMessage="Start a journey in another country" />
            </Button>
          </VStack>
        </Page.Body>
      </Page>
    );
  }

  if (!currentLevel) {
    return (
      <Page>
        <Page.Body>
          <Text color="red.500" textAlign="center">
            <FormattedMessage id="birdr_journey_no_levels" defaultMessage="No journey levels configured yet." />
          </Text>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <VStack gap={1} align="center">
          <Text fontSize="sm" fontWeight="600" color="primary.600">
            {countryName}
          </Text>
          {languageGhost}
          <Text fontSize="lg" fontWeight="700" color="primary.800" textAlign="center">
            <FormattedMessage
              id="birdr_journey_level_n"
              defaultMessage="Level {n}"
              values={{ n: currentLevel.sequence }}
            />
            {currentTitle ? ` — ${currentTitle}` : ''}
          </Text>
        </VStack>
      </Page.Header>
      <Page.Body>
        {!isAuthenticated && (
          <Box
            bg="orange.50"
            borderWidth="1px"
            borderColor="orange.300"
            borderRadius="md"
            p={3}
            mb={4}
          >
            <Text fontSize="sm" color="primary.800" lineHeight="tall">
              <FormattedMessage id="birdr_journey_guest_save_hint" defaultMessage="Sign up to save progress on all your devices." />
            </Text>
          </Box>
        )}

        <BirdrJourneyStepTrail
          currentLevel={currentLevel}
          nextLevel={journey.next_level}
          onStepPress={handleStepPress}
          canPlay={hasPlayableStep(journey)}
        />
      </Page.Body>
    </Page>
  );
}
