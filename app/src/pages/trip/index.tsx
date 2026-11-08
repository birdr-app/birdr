import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { countryCodeToFlag } from '../../api/birdrJourney';
import { unitKnown } from '../../core/trip-quiz';
import { fetchTrips, fetchTripProgress, loadTripState, type TripRegion, type TripSummary, type TripUnit } from '../../api/trip';
import { Page } from '../../shared/components/layout';
import { Kicker } from '../course/parts';
import { ProgressRing, TripLoading, UnitRow } from './parts';
import { TripRequestForm } from './request';
import { orderedUnits, useTrip, useTripLang, useTripText } from './use-trip';

/** /trips: the countries with Trip prep. */
export function TripListPage() {
  const t = useTripText();
  const lang = useTripLang();
  const navigate = useNavigate();
  const [trips, setTrips] = useState<TripSummary[] | null>(null);
  const [error, setError] = useState(false);
  const load = () => {
    setError(false);
    fetchTrips(lang)
      .then(setTrips)
      .catch(() => setError(true));
  };
  useEffect(load, [lang]);

  if (!trips) return <TripLoading error={error} onRetry={load} />;
  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="2xl">
          {t('trip_title', 'Trip prep')}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          <Text color="primary.800">
            {t('trip_list_intro', "Going abroad? Learn the birds before you go: first the kinds of birds, then the species, group by group. Birds you already know from other games count straight away.")}
          </Text>
          {trips.filter((trip) => !trip.parent).map((trip) => (
            <Button
              key={trip.country}
              variant="outline"
              height="auto"
              py={3}
              px={4}
              justifyContent="flex-start"
              whiteSpace="normal"
              bg="white"
              borderColor="primary.200"
              borderRadius="xl"
              onClick={() => navigate(`/trips/${trip.country}`)}
            >
              <Flex align="center" gap={3} w="full" textAlign="left">
                <Text fontSize="3xl">{countryCodeToFlag(trip.country)}</Text>
                <Box flex={1}>
                  <Text fontSize="lg" fontWeight="700" color="primary.800">
                    {trip.name}
                  </Text>
                  <Text fontSize="sm" color="primary.700">
                    {t('trip_list_counts', '{species} species · {endemics} endemics', {
                      species: trip.species_count,
                      endemics: trip.endemic_count,
                    })}
                  </Text>
                </Box>
              </Flex>
            </Button>
          ))}
          <TripRequestForm />
        </Flex>
      </Page.Body>
    </Page>
  );
}

/** How many birds of each region pack the player knows: from their answers anywhere, plus this device. */
function useRegionKnown(regions: TripRegion[]): Record<string, number> {
  const [known, setKnown] = useState<Record<string, number>>({});
  const key = regions.map((r) => r.country).join(',');
  useEffect(() => {
    let live = true;
    regions.forEach((region) => {
      fetchTripProgress(region.country).then((progress) => {
        const right = loadTripState(region.country).right;
        const count = new Set([...progress.known, ...right]).size;
        if (live) setKnown((old) => ({ ...old, [region.country]: count }));
      });
    });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return known;
}

/** /trips/:country: the trip's home, with the main progress number and what to do next. */
export function TripHomePage() {
  const { country: countryParam = '' } = useParams();
  const country = countryParam.toUpperCase();
  const t = useTripText();
  const navigate = useNavigate();
  const { trip, error, reload, local, known, knownGroups, progress } = useTrip(country);
  const [showKnown, setShowKnown] = useState(false);
  const regionKnown = useRegionKnown(trip?.regions ?? []);

  if (!trip) return <TripLoading error={error} onRetry={reload} />;

  const codes = Object.keys(trip.species);
  const knownCount = codes.filter((c) => known.has(c)).length;
  const endemicCodes = codes.filter((c) => trip.species[c].endemic);
  const endemicsKnown = endemicCodes.filter((c) => known.has(c)).length;
  const done = new Set(local.units_done);
  const units = orderedUnits(trip, knownGroups);
  const unitImage = (unit: TripUnit) => trip.species[unit.species[0]]?.images[0]?.url;
  const knownIn = (unit: TripUnit) => unit.species.filter((c) => known.has(c)).length;
  // A unit counts as done when it was played, or when the player knows every bird in it already.
  const isDone = (unit: TripUnit) => done.has(unit.slug) || unitKnown(unit.species, known);
  const openUnits = units.filter((u) => !unitKnown(u.species, known));
  const knownUnits = units.filter((u) => unitKnown(u.species, known));
  const knownUnitBirds = knownUnits.reduce((n, u) => n + u.species.length, 0);
  const familiesDone = local.families_done || trip.groups.every((g) => knownGroups.has(g.slug));
  // A region pack adds birds to the country's trip: no families, first day or endemics of its own.
  const isPack = !!trip.parent;
  const regions = trip.regions ?? [];
  const lookalikes = trip.lookalikes ?? [];
  const lookalikesKnown = lookalikes.filter((p) => known.has(p.here)).length;
  const lookalikeImage = lookalikes.length
    ? (trip.home_species?.[lookalikes[0].home] ?? trip.species[lookalikes[0].home])?.images[0]?.url
    : undefined;

  // What to do next: the families, the first day, the lookalikes, then the next unit.
  let next: { label: string; title: string; go: () => void } | null = null;
  if (!isPack && !familiesDone) {
    next = { label: t('trip_start_here', 'Start here'), title: t('trip_families_title', 'Meet the families'), go: () => navigate(`/trips/${country}/families`) };
  } else if (!isPack && !isDone(trip.first_day)) {
    next = { label: t('trip_next', 'Next'), title: trip.first_day.title, go: () => navigate(`/trips/${country}/units/${trip.first_day.slug}`) };
  } else if (!isPack && lookalikes.length && !local.lookalikes_done) {
    next = { label: t('trip_next', 'Next'), title: t('trip_lookalikes_title', 'Lookalikes from home'), go: () => navigate(`/trips/${country}/lookalikes`) };
  } else {
    const unit = units.find((u) => !isDone(u));
    if (unit) next = { label: t('trip_next', 'Next'), title: unit.title, go: () => navigate(`/trips/${country}/units/${unit.slug}`) };
  }

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="2xl">
          {countryCodeToFlag(trip.parent || country)}{' '}
          {t('trip_get_ready', 'Get ready for {country}', { country: isPack ? `${trip.parent_name}: ${trip.name}` : trip.name })}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          <Flex align="center" gap={4} bg="secondary.700" borderRadius="xl" p={4}>
            <ProgressRing value={codes.length ? knownCount / codes.length : 0} />
            <Box flex={1} minW={0}>
              <Text color="white" fontSize="lg" fontWeight="700">
                {t('trip_known_count', '{known} of {total} species', { known: knownCount, total: codes.length })}
              </Text>
              <Text color="secondary.100" fontSize="sm">
                {endemicCodes.length ? `${t('trip_endemics_count', 'Endemics {known}/{total}', { known: endemicsKnown, total: endemicCodes.length })} · ` : ''}
                {t('trip_units_count', 'Units {done}/{total}', {
                  done: trip.units.filter(isDone).length,
                  total: trip.units.length,
                })}
              </Text>
              {progress && progress.known.length > 0 && knownCount > 0 ? (
                <Text color="secondary.100" fontSize="xs" mt={1}>
                  {t('trip_known_hint', 'Includes birds you answered right in other games.')}
                </Text>
              ) : null}
            </Box>
          </Flex>

          {next ? (
            <Box bg="white" borderRadius="xl" p={4} borderWidth="2px" borderColor="primary.200">
              <Kicker>{next.label}</Kicker>
              <Text fontSize="xl" fontWeight="700" color="primary.800" mb={3}>
                {next.title}
              </Text>
              <Button colorPalette="primary" w="full" onClick={next.go}>
                {t('trip_continue', 'Continue')}
              </Button>
            </Box>
          ) : (
            <Box bg="white" borderRadius="xl" p={4} borderWidth="2px" borderColor="primary.200">
              <Text fontSize="xl" fontWeight="700" color="primary.800">
                {t('trip_all_done', "You've done every unit. Have a great trip.")}
              </Text>
            </Box>
          )}

          {trip.intro ? <Text color="primary.800">{trip.intro}</Text> : null}

          {!isPack ? (
            <Text fontSize="lg" fontWeight="700" color="primary.800" mt={2}>
              {t('trip_start_section', 'Get started')}
            </Text>
          ) : null}
          {!isPack ? <UnitRow
            title={t('trip_families_title', 'Meet the families')}
            subtitle={t('trip_groups_count', '{count} groups', { count: trip.groups.length })}
            image={trip.species[trip.groups[0]?.species[0]]?.images[0]?.url}
            known={knownGroups.size ? trip.groups.filter((g) => knownGroups.has(g.slug)).length : 0}
            total={trip.groups.length}
            done={familiesDone}
            onClick={() => navigate(`/trips/${country}/families`)}
          /> : null}
          {!isPack ? <UnitRow
            title={trip.first_day.title}
            subtitle={`${knownIn(trip.first_day)}/${trip.first_day.species.length}`}
            image={unitImage(trip.first_day)}
            known={knownIn(trip.first_day)}
            total={trip.first_day.species.length}
            done={isDone(trip.first_day)}
            onClick={() => navigate(`/trips/${country}/units/${trip.first_day.slug}`)}
          /> : null}
          {lookalikes.length ? (
            <UnitRow
              title={t('trip_lookalikes_title', 'Lookalikes from home')}
              subtitle={t('trip_pairs_count', '{count} pairs', { count: lookalikes.length })}
              image={lookalikeImage}
              known={lookalikesKnown}
              total={lookalikes.length}
              done={local.lookalikes_done}
              onClick={() => navigate(`/trips/${country}/lookalikes`)}
            />
          ) : null}
          {endemicCodes.length ? (
            <UnitRow
              title={t('trip_endemics_title', 'Endemics of {country}', { country: trip.name })}
              subtitle={`${endemicsKnown}/${endemicCodes.length}`}
              image={trip.species[endemicCodes[0]]?.images[0]?.url}
              known={endemicsKnown}
              total={endemicCodes.length}
              done={trip.endemics.units.every((u) => done.has(u.slug))}
              onClick={() => navigate(`/trips/${country}/endemics`)}
            />
          ) : null}

          {regions.length ? (
            <>
              <Text fontSize="lg" fontWeight="700" color="primary.800" mt={2}>
                {t('trip_regions_section', 'Regions')}
              </Text>
              <Text fontSize="sm" color="primary.700">
                {t('trip_regions_hint', 'More birds for the places you visit. They come on top of the {country} list.', { country: trip.name })}
              </Text>
              {regions.map((region) => (
                <UnitRow
                  key={region.country}
                  title={region.name}
                  image={region.image ?? undefined}
                  subtitle={t('trip_region_species', '{count} extra species', { count: region.species_count })}
                  known={regionKnown[region.country] ?? 0}
                  total={region.species_count}
                  done={(regionKnown[region.country] ?? 0) >= region.species_count}
                  onClick={() => navigate(`/trips/${region.country}`)}
                />
              ))}
            </>
          ) : null}

          <Text fontSize="lg" fontWeight="700" color="primary.800" mt={2}>
            {t('trip_units_section', 'Units')}
          </Text>
          <Text fontSize="sm" color="primary.700">
            {t('trip_units_hint', 'Groups that are new to you come first.')}
          </Text>
          {[...openUnits, ...(showKnown ? knownUnits : [])].map((unit) => (
            <UnitRow
              key={unit.slug}
              title={unit.title}
              subtitle={`${knownIn(unit)}/${unit.species.length}`}
              image={unitImage(unit)}
              known={knownIn(unit)}
              total={unit.species.length}
              done={isDone(unit)}
              highlight={next?.title === unit.title}
              onClick={() => navigate(`/trips/${country}/units/${unit.slug}`)}
            />
          ))}
          {knownUnits.length ? (
            <Button variant="ghost" colorPalette="primary" size="sm" onClick={() => setShowKnown(!showKnown)}>
              {showKnown
                ? t('trip_hide_known_units', 'Hide the units you know')
                : t('trip_show_known_units', 'You already know every bird in {count} units ({birds} birds). Show them', {
                    count: knownUnits.length,
                    birds: knownUnitBirds,
                  })}
            </Button>
          ) : null}
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default TripHomePage;
