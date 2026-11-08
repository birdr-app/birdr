import React, { useEffect } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { TripUnit } from '../api/trip';
import { Kicker, TripLoading, TripRing, UnitRow, tripStyles } from '../components/TripParts';
import { useRegionKnown, useTrip } from '../hooks/useTrip';
import { useTranslation } from '../i18n/TranslationContext';
import { leagueFlag } from '../lib/league';
import { orderedUnits } from '../lib/tripQuiz';
import { colors } from '../theme';

export type TripRoutes = {
  TripHome: { country: string };
  TripFamilies: { country: string };
  TripUnit: { country: string; slug: string };
  TripEndemics: { country: string };
};

/** The trip's home: the main progress number and what to do next. */
export function TripHomeScreen() {
  const route = useRoute<RouteProp<TripRoutes, 'TripHome'>>();
  const navigation = useNavigation<NativeStackNavigationProp<TripRoutes>>();
  const country = route.params.country.toUpperCase();
  const { t } = useTranslation();
  const { trip, error, reload, local, known, knownGroups, progress } = useTrip(country);
  const regionKnown = useRegionKnown(trip?.regions ?? []);

  useEffect(() => {
    if (trip) navigation.setOptions({ title: `${leagueFlag(trip.parent || country)} ${trip.name}` });
  }, [trip, country, navigation]);

  if (!trip) return <TripLoading error={error} onRetry={reload} />;

  const codes = Object.keys(trip.species);
  const knownCount = codes.filter((c) => known.has(c)).length;
  const endemicCodes = codes.filter((c) => trip.species[c].endemic);
  const endemicsKnown = endemicCodes.filter((c) => known.has(c)).length;
  const done = new Set(local.units_done);
  const units = orderedUnits(trip, knownGroups);
  const unitImage = (unit: TripUnit) => trip.species[unit.species[0]]?.images[0]?.url;
  const knownIn = (unit: TripUnit) => unit.species.filter((c) => known.has(c)).length;
  // A region pack adds birds to the country's trip: no families, first day or endemics of its own.
  const isPack = !!trip.parent;
  const regions = trip.regions ?? [];
  const openUnit = (slug: string) => navigation.navigate('TripUnit', { country, slug });

  // What to do next: the families, then the first day, then the next unit.
  let next: { label: string; title: string; go: () => void } | null = null;
  if (!isPack && !local.families_done) {
    next = { label: t('trip_start_here'), title: t('trip_families_title'), go: () => navigation.navigate('TripFamilies', { country }) };
  } else if (!isPack && !done.has(trip.first_day.slug)) {
    next = { label: t('trip_next'), title: trip.first_day.title, go: () => openUnit(trip.first_day.slug) };
  } else {
    const unit = units.find((u) => !done.has(u.slug));
    if (unit) next = { label: t('trip_next'), title: unit.title, go: () => openUnit(unit.slug) };
  }

  return (
    <ScrollView style={tripStyles.container} contentContainerStyle={tripStyles.content}>
      <View style={styles.hero}>
        <TripRing value={codes.length ? knownCount / codes.length : 0} />
        <View style={tripStyles.flex}>
          <Text style={styles.heroKicker}>{t('trip_get_ready', { country: isPack ? `${trip.parent_name}: ${trip.name}` : trip.name })}</Text>
          <Text style={styles.heroTitle}>{t('trip_known_count', { known: knownCount, total: codes.length })}</Text>
          <Text style={styles.heroLine}>
            {endemicCodes.length ? `${t('trip_endemics_count', { known: endemicsKnown, total: endemicCodes.length })} · ` : ''}
            {t('trip_units_count', { done: trip.units.filter((u) => done.has(u.slug)).length, total: trip.units.length })}
          </Text>
          {progress && progress.known.length > 0 && knownCount > 0 ? (
            <Text style={styles.heroHint}>{t('trip_known_hint')}</Text>
          ) : null}
        </View>
      </View>

      {next ? (
        <View style={[tripStyles.card, tripStyles.cardStrong]}>
          <Kicker>{next.label}</Kicker>
          <Text style={styles.nextTitle}>{next.title}</Text>
          <TouchableOpacity style={tripStyles.primaryButton} onPress={next.go} accessibilityRole="button" testID="trip.next">
            <Text style={tripStyles.primaryButtonText}>{t('trip_continue')}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={[tripStyles.card, tripStyles.cardStrong]}>
          <Text style={styles.nextTitle}>{t('trip_all_done')}</Text>
        </View>
      )}

      {trip.intro ? <Text style={tripStyles.body}>{trip.intro}</Text> : null}

      {!isPack ? <Text style={tripStyles.sectionTitle}>{t('trip_start_section')}</Text> : null}
      {!isPack ? <UnitRow
        title={t('trip_families_title')}
        subtitle={t('trip_groups_count', { count: trip.groups.length })}
        image={trip.species[trip.groups[0]?.species[0]]?.images[0]?.url}
        known={trip.groups.filter((g) => knownGroups.has(g.slug)).length}
        total={trip.groups.length}
        done={local.families_done}
        onPress={() => navigation.navigate('TripFamilies', { country })}
        testID="trip.families"
      /> : null}
      {!isPack ? <UnitRow
        title={trip.first_day.title}
        subtitle={`${knownIn(trip.first_day)}/${trip.first_day.species.length}`}
        image={unitImage(trip.first_day)}
        known={knownIn(trip.first_day)}
        total={trip.first_day.species.length}
        done={done.has(trip.first_day.slug)}
        onPress={() => openUnit(trip.first_day.slug)}
        testID="trip.firstDay"
      /> : null}
      {endemicCodes.length ? (
        <UnitRow
          title={t('trip_endemics_title', { country: trip.name })}
          subtitle={`${endemicsKnown}/${endemicCodes.length}`}
          image={trip.species[endemicCodes[0]]?.images[0]?.url}
          known={endemicsKnown}
          total={endemicCodes.length}
          done={trip.endemics.units.length > 0 && trip.endemics.units.every((u) => done.has(u.slug))}
          onPress={() => navigation.navigate('TripEndemics', { country })}
          testID="trip.endemics"
        />
      ) : null}

      {regions.length ? (
        <>
          <Text style={tripStyles.sectionTitle}>{t('trip_regions_section')}</Text>
          <Text style={tripStyles.small}>{t('trip_regions_hint', { country: trip.name })}</Text>
          {regions.map((region) => (
            <UnitRow
              key={region.country}
              title={region.name}
              image={region.image ?? undefined}
              subtitle={t('trip_region_species', { count: region.species_count })}
              known={regionKnown[region.country] ?? 0}
              total={region.species_count}
              done={(regionKnown[region.country] ?? 0) >= region.species_count}
              onPress={() => navigation.push('TripHome', { country: region.country })}
              testID={`trip.region.${region.country}`}
            />
          ))}
        </>
      ) : null}

      <Text style={tripStyles.sectionTitle}>{t('trip_units_section')}</Text>
      <Text style={tripStyles.small}>{t('trip_units_hint')}</Text>
      {units.map((unit) => (
        <UnitRow
          key={unit.slug}
          title={unit.title}
          subtitle={`${knownIn(unit)}/${unit.species.length}`}
          image={unitImage(unit)}
          known={knownIn(unit)}
          total={unit.species.length}
          done={done.has(unit.slug)}
          highlight={next?.title === unit.title}
          onPress={() => openUnit(unit.slug)}
          testID={`trip.unit.${unit.slug}`}
        />
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  hero: { flexDirection: 'row', alignItems: 'center', gap: 16, backgroundColor: colors.secondary[700], borderRadius: 16, padding: 16 },
  heroKicker: { color: colors.secondary[100], fontSize: 13, fontWeight: '700' },
  heroTitle: { color: '#fff', fontSize: 18, fontWeight: '700', marginTop: 2 },
  heroLine: { color: colors.secondary[100], fontSize: 14, marginTop: 2 },
  heroHint: { color: colors.secondary[100], fontSize: 12, marginTop: 4 },
  nextTitle: { fontSize: 20, fontWeight: '700', color: colors.primary[800] },
});
