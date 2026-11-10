import { Box, Flex, Heading, Text } from '@chakra-ui/react';
import { useNavigate, useParams } from 'react-router-dom';
import { Page } from '../../shared/components/layout';
import { Kicker } from '../course/parts';
import { TripBackLink, TripLoading, UnitRow } from './parts';
import { useTrip, useTripText } from './use-trip';

/** /trips/:country/endemics: why the country has its own birds, where they live, and their units. */
export function TripEndemicsPage() {
  const { country: countryParam = '' } = useParams();
  const country = countryParam.toUpperCase();
  const t = useTripText();
  const navigate = useNavigate();
  const { trip, error, reload, known, local } = useTrip(country);
  if (!trip) return <TripLoading error={error} onRetry={reload} />;
  const done = new Set(local.units_done);
  const { endemics } = trip;
  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="xl">
          {t('trip_endemics_title', 'Endemics of {country}', { country: trip.name })}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          <TripBackLink to={trip.country} name={trip.name} />
          {endemics.why_here ? <Text color="primary.800" lineHeight="1.6">{endemics.why_here}</Text> : null}
          {endemics.where.length ? (
            <>
              <Kicker>{t('trip_where_to_find', 'Where to find them')}</Kicker>
              {endemics.where.map((card) => (
                <Box key={card.title} bg="white" borderRadius="lg" p={3} borderWidth="1px" borderColor="primary.200">
                  <Text fontWeight="700" color="primary.800">
                    {card.title}
                  </Text>
                  <Text fontSize="sm" color="primary.800">
                    {card.text}
                  </Text>
                </Box>
              ))}
            </>
          ) : null}
          {endemics.families.map((card) => (
            <Box key={card.title} bg="secondary.50" borderRadius="lg" p={3}>
              <Text fontWeight="700" color="primary.800">
                {card.title}
              </Text>
              <Text fontSize="sm" color="primary.800">
                {card.text}
              </Text>
            </Box>
          ))}
          <Kicker>{t('trip_the_birds', 'The birds')}</Kicker>
          {endemics.units.map((unit) => {
            const knownIn = unit.species.filter((c) => known.has(c)).length;
            return (
              <UnitRow
                key={unit.slug}
                title={unit.title}
                subtitle={`${knownIn}/${unit.species.length}`}
                image={trip.species[unit.species[0]]?.images[0]?.url}
                known={knownIn}
                total={unit.species.length}
                done={done.has(unit.slug)}
                onClick={() => navigate(`/trips/${country}/units/${unit.slug}`)}
              />
            );
          })}
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default TripEndemicsPage;
