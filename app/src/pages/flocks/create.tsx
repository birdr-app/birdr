import React, { useEffect, useState } from 'react';
import {
  Alert,
  AlertContent,
  AlertIndicator,
  AlertTitle,
  Box,
  Button,
  Container,
  Field,
  Heading,
  Input,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  createFlock,
  getFlockDetailPath,
  getFlocksJoinPath,
  setStoredMainFlockSlug,
} from '../../api/flocks';
import CountryCombobox from '../../components/country-combobox';
import { useAuthProfile } from '../../core/auth-profile-context';
import { Page } from '../../shared/components/layout';
import { UseCountries, type Country } from '../../user/use-countries';

export function FlocksCreatePage() {
  const navigate = useNavigate();
  const intl = useIntl();
  const { isAuthenticated, ready } = useAuthProfile();
  const { countries } = UseCountries();
  const countriesList = Array.isArray(countries) ? countries : [];

  const [name, setName] = useState('');
  const [country, setCountry] = useState<Country | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/flocks/create' }, replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  const handleCreate = async () => {
    if (!name.trim() || !country?.code) return;
    setCreating(true);
    setError(null);
    try {
      const flock = await createFlock({
        name: name.trim(),
        country_code: country.code,
      });
      setStoredMainFlockSlug(flock.slug);
      navigate(getFlockDetailPath(flock.slug), { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create flock');
    } finally {
      setCreating(false);
    }
  };

  if (!ready || !isAuthenticated) return null;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="flocks_create" defaultMessage="Create flock" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.md" py={4}>
          <Text color="primary.700" mb={6}>
            <FormattedMessage
              id="flocks_intro_step_create"
              defaultMessage="Create a flock for your club or group of friends"
            />
          </Text>

          {error && (
            <Alert.Root status="error" mb={4}>
              <AlertIndicator />
              <AlertContent>
                <AlertTitle>{error}</AlertTitle>
              </AlertContent>
            </Alert.Root>
          )}

          <VStack align="stretch" gap={4}>
            <Field.Root required>
              <Field.Label>
                <FormattedMessage id="flocks_name" defaultMessage="Flock name" />
              </Field.Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </Field.Root>
            <Box>
              <Text mb={2} fontSize="sm" fontWeight="600">
                <FormattedMessage id="country" defaultMessage="Country" />
              </Text>
              <CountryCombobox
                countries={countriesList}
                value={country}
                onChange={setCountry}
                excludeRegionCodes
                placeholder={intl.formatMessage({
                  id: 'flocks_select_country',
                  defaultMessage: 'Default quiz country',
                })}
              />
            </Box>
            <Button
              colorPalette="primary"
              size="lg"
              loading={creating}
              disabled={!name.trim() || !country?.code}
              onClick={() => void handleCreate()}
            >
              <FormattedMessage id="flocks_create_submit" defaultMessage="Create" />
            </Button>
            <Button variant="ghost" colorPalette="primary" onClick={() => navigate(getFlocksJoinPath())}>
              <FormattedMessage
                id="flocks_intro_join_instead"
                defaultMessage="I already have an invite"
              />
            </Button>
          </VStack>
        </Container>
      </Page.Body>
    </Page>
  );
}

export default FlocksCreatePage;
