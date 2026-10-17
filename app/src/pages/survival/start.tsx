import { useContext, useEffect, useState } from 'react';
import { Box, Button, Flex, Heading, Icon, Text } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import { FaCrown, FaStar } from 'react-icons/fa';
import AppContext from '../../core/app-context';
import { Page } from '../../shared/components/layout';
import { SetName } from '../../components/set-name';
import SelectLanguage from '../../components/select-language';
import SelectCountry from '../../components/select-country';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { fetchSurvivalRecord, type SurvivalRecordResponse } from '../../api/survival';
import { getCountryDisplayName } from '../../data/country-names-nl';
import { useStartSurvival } from './use-start-survival';

export function SurvivalRecordCard({
  record,
  loading,
}: {
  record: SurvivalRecordResponse | null;
  loading?: boolean;
}) {
  const countryRecord = record?.country_record;
  return (
    <Flex gap={3} wrap="wrap">
      <Flex
        flex="1"
        minW="140px"
        align="center"
        gap={3}
        p={3}
        bg="primary.100"
        borderRadius="lg"
        borderWidth="1px"
        borderColor="primary.200"
      >
        <Icon as={FaCrown} color="#eab308" boxSize={6} />
        <Box>
          <Text fontSize="xs" fontWeight="600" color="primary.600" textTransform="uppercase">
            <FormattedMessage id="survival_country_record" defaultMessage="Country record" />
          </Text>
          <Text fontSize="lg" fontWeight="800" color="primary.800">
            {loading ? '…' : countryRecord ? countryRecord.streak : '–'}
          </Text>
          {countryRecord?.name ? (
            <Text fontSize="xs" color="primary.600" truncate>
              {countryRecord.name}
            </Text>
          ) : null}
        </Box>
      </Flex>
      <Flex
        flex="1"
        minW="140px"
        align="center"
        gap={3}
        p={3}
        bg="primary.100"
        borderRadius="lg"
        borderWidth="1px"
        borderColor="primary.200"
      >
        <Icon as={FaStar} color="primary.500" boxSize={6} />
        <Box>
          <Text fontSize="xs" fontWeight="600" color="primary.600" textTransform="uppercase">
            <FormattedMessage id="survival_personal_best" defaultMessage="Your best" />
          </Text>
          <Text fontSize="lg" fontWeight="800" color="primary.800">
            {loading ? '…' : (record?.personal_best ?? 0)}
          </Text>
        </Box>
      </Flex>
    </Flex>
  );
}

export function SurvivalStartPage() {
  const navigate = useNavigate();
  const { country, language, playerName, player, appLanguage } = useContext(AppContext);
  const { start, starting, error } = useStartSurvival();
  const [record, setRecord] = useState<SurvivalRecordResponse | null>(null);
  const [recordLoading, setRecordLoading] = useState(false);
  const countryCode = country?.code ?? '';

  useEffect(() => {
    if (!countryCode) {
      setRecord(null);
      return;
    }
    let cancelled = false;
    setRecordLoading(true);
    fetchSurvivalRecord(countryCode)
      .then((data) => {
        if (!cancelled) setRecord(data);
      })
      .catch(() => {
        if (!cancelled) setRecord(null);
      })
      .finally(() => {
        if (!cancelled) setRecordLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [countryCode]);

  const canStart = Boolean(countryCode && (playerName?.trim() || player?.name));

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="survival" defaultMessage="Survival" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={8}>
          <Flex align="center" gap={4}>
            <BirdrArtImage
              filename="birdr-survival.png"
              alt=""
              width="88px"
              height="88px"
              objectFit="contain"
              bg="transparent"
              flexShrink={0}
            />
            <Text color="primary.800">
              <FormattedMessage
                id="survival_intro"
                defaultMessage="How long can you last? Pro level, 15 seconds per bird. One mistake and it's over."
              />
            </Text>
          </Flex>

          {countryCode ? <SurvivalRecordCard record={record} loading={recordLoading} /> : null}

          <SetName />
          <SelectLanguage />
          <SelectCountry />

          {error ? <Text color="red.600">{error}</Text> : null}

          <Button
            size="lg"
            colorPalette="primary"
            disabled={!canStart || starting}
            loading={starting}
            onClick={() =>
              void start({
                country: countryCode,
                countryName: getCountryDisplayName(country, appLanguage || 'en'),
                language: language || 'en',
                source: 'start',
              })
            }
          >
            <FormattedMessage id="survival_start" defaultMessage="Start survival" />
          </Button>
          <Button
            variant="ghost"
            colorPalette="primary"
            onClick={() =>
              navigate(`/survival/scores${countryCode ? `?country=${encodeURIComponent(countryCode)}` : ''}`)
            }
          >
            <FormattedMessage id="survival_highscores" defaultMessage="Survival high scores" />
          </Button>
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default SurvivalStartPage;
