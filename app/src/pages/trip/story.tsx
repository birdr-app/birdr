import { Text } from '@chakra-ui/react';
import type { Trip } from '../../api/trip';
import { useTripLang } from './use-trip';

/** Why the prep is built the way it is: birds on record, the first course, the bonus rounds. */
export function TripStory({ trip }: { trip: Trip }) {
  const lang = useTripLang();
  const c = trip.counts;
  if (!c?.recorded) return null;
  const text =
    lang === 'nl'
      ? `Er zijn ${c.recorded} vogelsoorten waargenomen in ${trip.name}. Veel daarvan zijn zeldzame gasten die je vrijwel nooit tegenkomt, dus bouwden we je voorbereiding rond de vogels die je echt gaat zien. De eerste cursus leert je de ${c.trip} soorten die de meeste reizigers tegenkomen, endemen inbegrepen, met tips waar je op moet letten.` +
        (c.plus ? ` Daarna volgen de bonusrondes: nog ${c.plus} gewone vogels waar een Gevorderd-spel naar kan vragen, zodat een echt spel je niet meer verrast.` : '')
      : `${c.recorded} bird species have been recorded in ${trip.name}. Many are rare visitors you will almost never meet, so we built your prep around the birds you will actually see. The first course teaches the ${c.trip} species most travellers come across, endemics included, with tips on what to look for.` +
        (c.plus ? ` Then come the bonus rounds: ${c.plus} more regular birds an Advanced game can ask about, so a real game holds no surprises.` : '');
  return <Text color="primary.800">{text}</Text>;
}
