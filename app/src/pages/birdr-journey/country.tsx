import { Box, Button, Spinner, Text, VStack } from '@chakra-ui/react';
import { useContext, useEffect, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  createBirdrJourneyPlayer,
  getStoredBirdrJourneyPlayerToken,
  startBirdrJourney,
} from '../../api/birdrJourney';
import CountryRegionSelect from '../../components/country-region-select';
import LanguageCombobox from '../../components/language-combobox';
import AppContext from '../../core/app-context';
import { persistCountryChallengeSpeciesLanguage } from '../../core/journey-species-language';
import { useAuthProfile } from '../../core/auth-profile-context';
import { Page } from '../../shared/components/layout';
import { statePickerParentCode } from '../../data/country-groups';
import { UseCountries, type Country } from '../../user/use-countries';
import { UseLanguages } from '../../user/use-languages';
import { resolveDefaultCountry, writeStoredCountryCode } from '../../user/country-preference';

export function BirdrJourneyCountryPage() {
  const navigate = useNavigate();
  const intl = useIntl();
  const { language, applySpeciesLanguage } = useContext(AppContext);
  const { isAuthenticated, profile, applyProfile } = useAuthProfile();
  const { countries } = UseCountries();
  const { languages } = UseLanguages();
  const [country, setCountry] = useState<Country | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!countries?.length) return;
    const filtered = countries.filter((c) => !c.code.includes('NL-NH'));
    const profileCode = isAuthenticated ? profile?.country_code ?? null : null;
    let cancelled = false;
    resolveDefaultCountry(filtered, profileCode).then((match) => {
      if (cancelled || !match) return;
      // The whole country is the default, even when a region was picked elsewhere in the app.
      const rootCode = statePickerParentCode(match);
      setCountry((rootCode && filtered.find((c) => c.code === rootCode)) || match);
    });
    return () => {
      cancelled = true;
    };
  }, [countries, isAuthenticated, profile?.country_code]);

  const ensureAuth = async (): Promise<boolean> => {
    if (isAuthenticated) return true;
    if (getStoredBirdrJourneyPlayerToken() || localStorage.getItem('player-token')) return true;
    try {
      await createBirdrJourneyPlayer('Guest', language || 'en');
      return true;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create player');
      return false;
    }
  };

  const handleConfirm = async () => {
    if (!country) {
      setError('Please select a country');
      return;
    }
    const ok = await ensureAuth();
    if (!ok) return;
    await persistCountryChallengeSpeciesLanguage({
      language: language || 'en',
      applySpeciesLanguage,
      isAuthenticated,
      applyProfile,
    });
    setSubmitting(true);
    setError(null);
    try {
      await startBirdrJourney(country.code);
      navigate(`/journey/${country.code}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start journey');
    } finally {
      setSubmitting(false);
    }
  };

  if (!countries?.length) {
    return (
      <Page>
        <Page.Body>
          <VStack py={12}>
            <Spinner size="lg" color="primary.500" />
          </VStack>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <FormattedMessage id="birdr_journey_select_country" defaultMessage="Choose your country" />
      </Page.Header>
      <Page.Body>
        <Text fontSize="md" color="primary.600" mb={6} lineHeight="tall">
          <FormattedMessage id="birdr_journey_country_hint" defaultMessage="Your journey uses birds found in this country." />
        </Text>

        <Text fontSize="sm" fontWeight="600" color="primary.700" mb={2}>
          <FormattedMessage id="country" defaultMessage="Country" />
        </Text>
        <Box mb={4}>
          <CountryRegionSelect
            countries={countries.filter((c) => !c.code.includes('NL-NH'))}
            value={country}
            onChange={(c) => {
              setCountry(c);
              if (c?.code) writeStoredCountryCode(c.code);
            }}
            allRegionsLabel={intl.formatMessage({ id: 'country_challenge_whole_country', defaultMessage: 'Whole country' })}
          />
        </Box>

        <Text fontSize="sm" fontWeight="600" color="primary.700" mb={2}>
          <FormattedMessage id="bird_name_language" defaultMessage="Bird name language" />
        </Text>
        <Box mb={4}>
          <LanguageCombobox
            languages={Array.isArray(languages) ? languages : []}
            value={language || 'en'}
            onChange={(code) => {
              void persistCountryChallengeSpeciesLanguage({
                language: code,
                applySpeciesLanguage,
                isAuthenticated,
                applyProfile,
              });
            }}
          />
        </Box>

        {!isAuthenticated && (
          <Text fontSize="sm" color="primary.600" mb={4} lineHeight="tall">
            <FormattedMessage id="birdr_journey_guest_save_hint" defaultMessage="Sign up to save progress on all your devices." />
          </Text>
        )}

        {error && (
          <Text color="red.500" fontSize="sm" mb={4}>
            {error}
          </Text>
        )}

        <Button
          colorPalette="primary"
          width="full"
          onClick={handleConfirm}
          loading={submitting}
        >
          <FormattedMessage id="birdr_journey_begin" defaultMessage="Start my journey" />
        </Button>
      </Page.Body>
    </Page>
  );
}
