import { Button, Flex, Heading, Spinner, Text } from '@chakra-ui/react';
import { useEffect, useMemo, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import type { CoursePhotoBird } from '../api/course-photos';
import { fetchTripPhotos, tripPhotoApi, type TripPhotoBird, type TripPhotos } from '../api/trip-photos';
import type { PhotoPick } from '../core/course-photo-roles';
import { useAuthProfile } from '../core/auth-profile-context';
import { Page } from '../shared/components/layout';
import { BirdPhotos, Centered } from './course-photos';

const toBird = (b: TripPhotoBird): CoursePhotoBird => ({
  species_id: b.species_id,
  name: b.name,
  latin: b.latin,
  plumage: '',
  file: b.file,
  pick: b.pick,
});

/** Staff page: choose the main, card and quiz photos of every bird in a trip prep pack. */
export function TripPhotosPage() {
  const { profile, ready } = useAuthProfile();
  const isStaff = !!(profile?.is_staff || profile?.is_superuser);
  const [trip, setTrip] = useState(() => {
    try {
      return localStorage.getItem('trip-photos-trip') || 'IBERIA';
    } catch {
      return 'IBERIA';
    }
  });
  const [data, setData] = useState<TripPhotos | null>(null);
  const [error, setError] = useState(false);
  const [section, setSection] = useState<string | null>(null);
  const intl = useIntl();
  const api = useMemo(() => tripPhotoApi(trip), [trip]);

  useEffect(() => {
    if (!isStaff) return;
    setData(null);
    setError(false);
    fetchTripPhotos(trip)
      .then((d) => {
        setData(d);
        setSection(d.sections[0]?.slug ?? null);
      })
      .catch(() => setError(true));
  }, [isStaff, trip]);

  const chooseTrip = (code: string) => {
    setTrip(code);
    try {
      localStorage.setItem('trip-photos-trip', code);
    } catch {
      // only a convenience
    }
  };

  const updateBird = (speciesId: number, pick: PhotoPick) =>
    setData((d) =>
      d
        ? { ...d, sections: d.sections.map((s) => ({ ...s, birds: s.birds.map((b) => (b.species_id === speciesId ? { ...b, pick } : b)) })) }
        : d
    );

  if (!ready) return <Centered><Spinner color="primary.500" /></Centered>;
  if (!isStaff) {
    return (
      <Centered>
        <Text>
          <FormattedMessage id="course_photos_staff_only" defaultMessage="This page is for Motmot admins." />
        </Text>
      </Centered>
    );
  }
  if (error) {
    return (
      <Centered>
        <Text>
          <FormattedMessage id="trip_photos_load_error" defaultMessage="The trip photos could not be loaded." />
        </Text>
      </Centered>
    );
  }
  if (!data) return <Centered><Spinner color="primary.500" /></Centered>;

  const current_trip = data.trips.find((t) => t.code === trip);
  const country = current_trip?.parent ?? trip;
  const countries = data.trips.filter((t) => !t.parent);
  const regions = data.trips.filter((t) => t.parent === country);
  const countryName = countries.find((t) => t.code === country)?.name ?? country;
  const allBirds = data.sections.flatMap((s) => s.birds);
  const doneCount = allBirds.filter((b) => b.pick?.done).length;
  const current = data.sections.find((s) => s.slug === section) ?? data.sections[0];

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="2xl">
          <FormattedMessage id="trip_photos_title" defaultMessage="Select trip photos" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={4} w="full">
          <Flex direction="column" gap={2}>
            <Flex gap={2} wrap="wrap">
              {countries.map((t) => (
                <Button key={t.code} size="sm" variant={t.code === country ? 'solid' : 'outline'} colorPalette="primary" onClick={() => chooseTrip(t.code)}>
                  {t.name}
                </Button>
              ))}
            </Flex>
            {regions.length > 0 && (
              <Flex gap={2} wrap="wrap" align="center" pl={3} borderLeftWidth="3px" borderColor="primary.200">
                <Text fontSize="xs" fontWeight="800" textTransform="uppercase" color="primary.600">
                  <FormattedMessage id="trip_photos_regions" defaultMessage="{country} packs" values={{ country: countryName }} />
                </Text>
                {[{ code: country, name: countryName }, ...regions].map((t) => (
                  <Button key={t.code} size="xs" variant={t.code === trip ? 'solid' : 'outline'} colorPalette="secondary" onClick={() => chooseTrip(t.code)}>
                    {t.code === country ? intl.formatMessage({ id: 'trip_photos_whole', defaultMessage: 'Whole country' }) : t.name}
                  </Button>
                ))}
              </Flex>
            )}
          </Flex>
          <Text color="primary.700" fontSize="sm">
            <FormattedMessage
              id="trip_photos_intro"
              defaultMessage="Tap a photo to make it the main photo, a card photo (max. 3) or a quiz photo, or to leave it out. Changes go live in the trip straight away. {done} of {total} birds done."
              values={{ done: doneCount, total: allBirds.length }}
            />
          </Text>
          <Flex gap={2} wrap="wrap">
            {data.sections.map((s) => {
              const finished = s.birds.length > 0 && s.birds.every((b) => b.pick?.done);
              return (
                <Button
                  key={s.slug}
                  size="sm"
                  variant={s.slug === current?.slug ? 'solid' : 'outline'}
                  colorPalette={finished ? 'secondary' : 'primary'}
                  onClick={() => {
                    setSection(s.slug);
                    window.scrollTo({ top: 0 });
                  }}
                >
                  {s.title}
                  {finished ? ' ✓' : ''}
                </Button>
              );
            })}
          </Flex>
          {current?.birds.map((b) => (
            <BirdPhotos
              key={`${trip}-${b.species_id}`}
              api={api}
              bird={toBird(b)}
              subtitle={b.name_nl || undefined}
              onSaved={(pick) => updateBird(b.species_id, pick)}
            />
          ))}
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default TripPhotosPage;
