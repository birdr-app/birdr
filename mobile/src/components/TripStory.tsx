import React from 'react';
import { Text } from 'react-native';
import type { Trip } from '../api/trip';
import { useTranslation } from '../i18n/TranslationContext';
import { tripStyles } from './TripParts';

/** Why the prep is built the way it is: birds on record, the first course, the bonus rounds. */
export function TripStory({ trip }: { trip: Trip }) {
  const { locale } = useTranslation();
  const c = trip.counts;
  const regions = (trip.regions ?? []).map((r) => r.name);
  const list = regions.join(', ');
  if (!c?.recorded) return null;
  const text =
    locale.slice(0, 2) === 'nl'
      ? `Er zijn ${c.recorded} vogelsoorten waargenomen in ${trip.name}. Veel daarvan zijn zeldzame gasten die je vrijwel nooit tegenkomt, dus bouwden we je voorbereiding rond de vogels die je echt gaat zien. De eerste cursus leert je de ${c.trip} soorten die de meeste reizigers tegenkomen, endemen inbegrepen, met tips waar je op moet letten.` +
        (c.plus ? ` Daarna volgen de bonusrondes: nog ${c.plus} gewone vogels waar een Gevorderd-spel naar kan vragen, zodat een echt spel je niet meer verrast.` : '') +
        (regions.length ? ` Reis je naar een bepaald deel van het land? Er zijn ook regiopakketten (${list}) met extra vogels voor die plekken; ze horen bij de bonusrondes, en je kunt ze bij je landtotaal optellen.` : '')
      : `${c.recorded} bird species have been recorded in ${trip.name}. Many are rare visitors you will almost never meet, so we built your prep around the birds you will actually see. The first course teaches the ${c.trip} species most travellers come across, endemics included, with tips on what to look for.` +
        (c.plus ? ` Then come the bonus rounds: ${c.plus} more regular birds an Advanced game can ask about, so a real game holds no surprises.` : '') +
        (regions.length ? ` Visiting one part of the country? Region packs (${list}) add the birds of those places; they belong to the bonus rounds, and you can add them to your country total.` : '');
  return <Text style={tripStyles.body}>{text}</Text>;
}
