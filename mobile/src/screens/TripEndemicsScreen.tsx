import React, { useEffect } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { TripBackLink, Kicker, TripLoading, UnitRow, tripStyles } from '../components/TripParts';
import { useTrip } from '../hooks/useTrip';
import { useTranslation } from '../i18n/TranslationContext';
import type { TripRoutes } from './TripHomeScreen';

/** Why the country has its own birds, where they live, and their units. */
export function TripEndemicsScreen() {
  const route = useRoute<RouteProp<TripRoutes, 'TripEndemics'>>();
  const navigation = useNavigation<NativeStackNavigationProp<TripRoutes>>();
  const country = route.params.country.toUpperCase();
  const { t } = useTranslation();
  const { trip, error, reload, known, local } = useTrip(country);

  useEffect(() => {
    if (trip) navigation.setOptions({ title: t('trip_endemics_title', { country: trip.name }) });
  }, [trip, navigation, t]);

  if (!trip) return <TripLoading error={error} onRetry={reload} />;
  const done = new Set(local.units_done);
  const { endemics } = trip;
  return (
    <ScrollView style={tripStyles.container} contentContainerStyle={tripStyles.content}>
      <TripBackLink country={trip.country} name={trip.name} />
      {endemics.why_here ? <Text style={tripStyles.body}>{endemics.why_here}</Text> : null}
      {endemics.where.length ? (
        <>
          <Kicker>{t('trip_where_to_find')}</Kicker>
          {endemics.where.map((card) => (
            <View key={card.title} style={[tripStyles.card, { gap: 4, padding: 12 }]}>
              <Text style={[tripStyles.body, { fontWeight: '700' }]}>{card.title}</Text>
              <Text style={tripStyles.small}>{card.text}</Text>
            </View>
          ))}
        </>
      ) : null}
      {endemics.families.map((card) => (
        <View key={card.title} style={tripStyles.greenNote}>
          <Text style={[tripStyles.body, { fontWeight: '700' }]}>{card.title}</Text>
          <Text style={tripStyles.small}>{card.text}</Text>
        </View>
      ))}
      <Kicker>{t('trip_the_birds')}</Kicker>
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
            onPress={() => navigation.navigate('TripUnit', { country, slug: unit.slug })}
            testID={`trip.unit.${unit.slug}`}
          />
        );
      })}
    </ScrollView>
  );
}
