import React, { useCallback, useState, useEffect, useMemo } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, Linking, ActivityIndicator, Image } from 'react-native';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { loadUpdates, UpdateListItem } from '../api/updates';
import { UpdateListItemCard } from '../components/UpdateListItemCard';
import {
  findInProgressBirdrJourney,
  getStoredBirdrJourneyCountryCode,
  type BirdrJourneyListItem,
} from '../api/birdrJourney';
import { listFlocks, pickMainFlock, setStoredMainFlockSlug, type Flock } from '../api/flocks';
import { BirdrLevelImage } from '../components/BirdrLevelImage';
import { GameArtImage } from '../components/GameArtImage';
import { colors } from '../theme';
import { getMoodImage } from '../constants/birdrMoodImages';
import { getFlockImage, getStartGameImage } from '../constants/birdrFlockImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { FeedbackForm } from '../components/FeedbackForm';
import { useSoftUpdateAvailable } from '../hooks/useSoftUpdateAvailable';
import { resolveMediaUrl } from '../api/config';
import {
  formatChallengeCountdown,
  getChallengeTimeRemaining,
} from '../utils/challengeCountdown';

function countryCodeToFlag(code: string): string {
  if (!code || code.length !== 2) return '';
  const base = 0x1f1e6;
  const c1 = code.charCodeAt(0) - 65;
  const c2 = code.charCodeAt(1) - 65;
  if (c1 < 0 || c1 > 25 || c2 < 0 || c2 > 25) return code;
  return String.fromCodePoint(base + c1, base + c2);
}

function levelTitle(
  level: { title: string; title_nl?: string } | null | undefined,
  locale: string
): string {
  if (!level) return '';
  if (locale === 'nl' && level.title_nl?.trim()) return level.title_nl;
  return level.title;
}

type RootStackParamList = {
  Home: undefined;
  Start: undefined;
  Scores: undefined;
  BirdrJourneyIntro: undefined;
  BirdrJourneyProgress: { countryCode: string };
  FlockIntro: undefined;
  FlockList: undefined;
  FlockDetail: { slug: string };
  Updates: undefined;
  UpdateDetail: { updateId: number };
  Help: undefined;
  Login: undefined;
};

export function HomeScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'Home'>>();
  const { t, locale } = useTranslation();
  const { visualStyle } = useVisualStyle();
  const { isAuthenticated } = useAuth();
  const { profile, ready: profileReady } = useProfile();
  const softUpdate = useSoftUpdateAvailable();
  const [updates, setUpdates] = useState<UpdateListItem[]>([]);
  const [activeJourney, setActiveJourney] = useState<BirdrJourneyListItem | null>(null);
  const [journeyLoading, setJourneyLoading] = useState(true);
  const [mainFlock, setMainFlock] = useState<Flock | null>(null);
  const [flocksLoading, setFlocksLoading] = useState(false);
  const [flocksReady, setFlocksReady] = useState(false);

  const loadFlockSummary = useCallback(async () => {
    if (!isAuthenticated) {
      setMainFlock(null);
      setFlocksReady(true);
      return;
    }
    setFlocksLoading(true);
    try {
      const flocks = await listFlocks();
      setMainFlock(await pickMainFlock(flocks));
    } catch {
      setMainFlock(null);
    } finally {
      setFlocksLoading(false);
      setFlocksReady(true);
    }
  }, [isAuthenticated]);

  const loadActiveJourney = useCallback(async () => {
    setJourneyLoading(true);
    try {
      const storedCountry = await getStoredBirdrJourneyCountryCode();
      const journey = await findInProgressBirdrJourney([
        storedCountry,
        isAuthenticated && profileReady && profile?.country_code ? profile.country_code : null,
      ]);
      setActiveJourney(journey);
    } catch {
      setActiveJourney(null);
    } finally {
      setJourneyLoading(false);
    }
  }, [profile?.country_code, profileReady, isAuthenticated]);

  useFocusEffect(
    useCallback(() => {
      loadUpdates(undefined, locale).then(setUpdates).catch(() => {});
      loadActiveJourney();
      loadFlockSummary();
    }, [loadActiveJourney, loadFlockSummary, locale])
  );

  useEffect(() => {
    if (!isAuthenticated) {
      setActiveJourney(null);
      setMainFlock(null);
      setFlocksReady(true);
    } else {
      setFlocksReady(false);
    }
    if (profileReady || !isAuthenticated) {
      loadActiveJourney();
    }
    if (isAuthenticated) {
      loadFlockSummary();
    }
  }, [isAuthenticated, profileReady, profile?.country_code, loadActiveJourney, loadFlockSummary]);

  const goJourneyProgress = () => {
    if (!activeJourney?.country?.code) return;
    navigation.navigate('BirdrJourneyProgress', { countryCode: activeJourney.country.code });
  };

  const goFlocks = async () => {
    if (mainFlock) {
      await setStoredMainFlockSlug(mainFlock.slug);
      navigation.navigate('FlockDetail', { slug: mainFlock.slug });
      return;
    }
    navigation.navigate('FlockIntro');
  };

  const countryCode = activeJourney?.country?.code ?? '';
  const countryLabel = activeJourney?.country
    ? getCountryDisplayName(activeJourney.country, locale)
    : '';
  const flag = countryCodeToFlag(countryCode);
  const currentLevelTitle = levelTitle(activeJourney?.current_level, locale);
  const flockLogoUri = resolveMediaUrl(mainFlock?.logo_url);
  const flockCountryLabel = mainFlock
    ? getCountryDisplayName(mainFlock.default_country, locale)
    : '';
  const flockChallenge = mainFlock?.active_challenge;

  const needsCountdown =
    !!flockChallenge &&
    flockChallenge.status === 'active' &&
    !flockChallenge.my_completed;

  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    if (!needsCountdown) return undefined;
    const id = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, [needsCountdown, flockChallenge?.id, flockChallenge?.ends_at]);

  const flockStatusLine = useMemo(() => {
    if (!flockChallenge) return t('flocks_no_active_challenge_short');
    if (flockChallenge.my_completed) {
      if (flockChallenge.my_rank_label) {
        return t('flocks_home_rank', { rank: flockChallenge.my_rank_label });
      }
      return t('flocks_home_completed');
    }
    const remaining = getChallengeTimeRemaining(flockChallenge.ends_at, new Date(nowTick));
    if (!remaining) return t('flocks_home_challenge_ended');
    return t('flocks_home_time_left', { time: formatChallengeCountdown(remaining) });
  }, [flockChallenge, nowTick, t]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {softUpdate.available && softUpdate.storeLabel && (
        <View style={styles.softUpdateCard}>
          <View style={styles.softUpdateText}>
            <Text style={styles.softUpdateTitle}>{t('update_available_title')}</Text>
            <Text style={styles.softUpdateMessage}>
              {t('update_available_message', { version: softUpdate.storeLabel })}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.softUpdateButton}
            onPress={() => Linking.openURL(softUpdate.storeUrl)}
            testID="home.updateAvailable"
            accessibilityRole="button"
            accessibilityLabel={t('update_available_button')}
          >
            <Text style={styles.softUpdateButtonText}>{t('update_available_button')}</Text>
          </TouchableOpacity>
        </View>
      )}
      {!isAuthenticated && (
        <View style={styles.signUpSection}>
          <TouchableOpacity
            style={styles.primaryButton}
            onPress={() => navigation.navigate('Login')}
          >
            <Text style={styles.primaryButtonText}>{t('sign_up')}</Text>
          </TouchableOpacity>
          <Text style={styles.signUpSubtext}>{t('sign_up_track_progress')}</Text>
        </View>
      )}
      <TouchableOpacity
        style={styles.startHeroButton}
        onPress={() => navigation.navigate('Start')}
        testID="home.startNewGame"
        accessibilityLabel={t('start_new_game')}
      >
        <GameArtImage
          source={getStartGameImage(visualStyle)}
          style={styles.startHeroImage}
          resizeMode="contain"
        />
        <View style={styles.startHeroText}>
          <Text style={styles.startHeroTitle}>{t('start_new_game')}</Text>
          <Text style={styles.startHeroHint}>{t('start_game_home_hint')}</Text>
        </View>
      </TouchableOpacity>

      <View style={styles.secondaryHeroColumn}>
        {journeyLoading ? (
          <View style={styles.secondaryLoadingWrap}>
            <ActivityIndicator size="small" color={colors.primary[500]} />
          </View>
        ) : activeJourney ? (
          <TouchableOpacity
            style={styles.journeyHeroButton}
            onPress={goJourneyProgress}
            testID="home.birdrJourneyContinue"
            accessibilityLabel={`${t('country_challenge')}, ${currentLevelTitle}, ${countryLabel}`}
          >
            <BirdrLevelImage
              iconUrl={activeJourney.current_level?.icon_url}
              sequence={activeJourney.current_level?.sequence}
              variant="current"
              size={56}
              framed={false}
            />
            <View style={styles.journeyHeroText}>
              <Text style={styles.journeyHeroLevel} numberOfLines={2}>
                {currentLevelTitle || t('country_challenge')}
              </Text>
              <Text style={styles.journeyHeroCountry} numberOfLines={1}>
                {flag ? `${flag} ` : ''}{countryLabel}
              </Text>
            </View>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={styles.journeyHeroButton}
            onPress={() => navigation.navigate('BirdrJourneyIntro')}
            testID="home.birdrJourney"
            accessibilityLabel={`${t('country_challenge')}, ${t('country_challenge_new_improved')}`}
          >
            <GameArtImage source={getMoodImage('success', visualStyle)} style={styles.journeyNewHeroImage} resizeMode="contain" />
            <View style={styles.journeyHeroText}>
              <Text style={styles.journeyHeroLevel} numberOfLines={2}>
                {t('country_challenge')}
              </Text>
              <Text style={styles.journeyHeroHint} numberOfLines={2}>
                {t('country_challenge_new_improved')}
              </Text>
            </View>
          </TouchableOpacity>
        )}

        {flocksLoading && !flocksReady ? (
          <View style={styles.secondaryLoadingWrap}>
            <ActivityIndicator size="small" color={colors.primary[500]} />
          </View>
        ) : mainFlock ? (
          <TouchableOpacity
            style={styles.flocksHeroButton}
            onPress={() => void goFlocks()}
            testID="home.flocks"
            accessibilityLabel={`${mainFlock.name}, ${flockCountryLabel}`}
          >
            {flockLogoUri ? (
              <Image source={{ uri: flockLogoUri }} style={styles.flocksHeroLogo} resizeMode="cover" />
            ) : (
              <GameArtImage
                source={getFlockImage('leaderboard', visualStyle)}
                style={styles.flocksHeroImage}
                resizeMode="contain"
              />
            )}
            <View style={styles.flocksHeroText}>
              <Text style={styles.flocksHeroTitle} numberOfLines={2}>
                {mainFlock.name}
              </Text>
              <Text style={styles.flocksHeroContinue} numberOfLines={1}>
                {flockStatusLine}
              </Text>
            </View>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={styles.flocksHeroButton}
            onPress={() => void goFlocks()}
            testID="home.flocks"
            accessibilityLabel={t('flocks_start')}
          >
            <GameArtImage
              source={getFlockImage('invite', visualStyle)}
              style={styles.flocksHeroImage}
              resizeMode="contain"
            />
            <View style={styles.flocksHeroText}>
              <Text style={styles.flocksHeroTitle} numberOfLines={2}>
                {t('flocks_start')}
              </Text>
              <Text style={styles.flocksHeroHint} numberOfLines={2}>
                {t('flocks_home_start_cta')}
              </Text>
            </View>
          </TouchableOpacity>
        )}
      </View>
      <FeedbackForm />
      {updates.length > 0 && (
        <UpdateListItemCard
          update={updates[0]}
          readMoreLabel={t('read_more')}
          style={styles.homeUpdateCard}
          onPress={() => navigation.navigate('UpdateDetail', { updateId: updates[0].id })}
        />
      )}
      <TouchableOpacity
        style={styles.ghostButton}
        onPress={() => navigation.navigate('Updates')}
      >
        <Text style={styles.ghostButtonText}>{t('more_updates')}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  content: {
    padding: 24,
    paddingTop: 16,
  },
  softUpdateCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.primary[50],
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  softUpdateText: {
    flex: 1,
    minWidth: 0,
  },
  softUpdateTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 2,
  },
  softUpdateMessage: {
    fontSize: 14,
    color: colors.primary[700],
    lineHeight: 20,
  },
  softUpdateButton: {
    backgroundColor: colors.primary[600],
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 8,
  },
  softUpdateButtonText: {
    color: colors.primary[50],
    fontSize: 15,
    fontWeight: '600',
  },
  signUpSection: {
    marginBottom: 24,
  },
  signUpSubtext: {
    fontSize: 14,
    color: colors.primary[600],
    textAlign: 'center',
    marginTop: 8,
  },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    color: colors.primary[50],
    fontSize: 16,
    fontWeight: '600',
  },
  startHeroButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    backgroundColor: colors.primary[500],
    paddingVertical: 18,
    paddingHorizontal: 18,
    borderRadius: 999,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.primary[400],
  },
  startHeroImage: {
    width: 88,
    height: 88,
  },
  startHeroText: {
    flex: 1,
    minWidth: 0,
  },
  startHeroTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.primary[50],
    lineHeight: 28,
    marginBottom: 4,
  },
  startHeroHint: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[100],
    lineHeight: 20,
  },
  secondaryHeroColumn: {
    width: '100%',
    gap: 12,
    marginBottom: 12,
  },
  secondaryLoadingWrap: {
    width: '100%',
    paddingVertical: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  journeyHeroButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.primary[800],
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: colors.primary[400],
  },
  journeyHeroText: {
    flex: 1,
    minWidth: 0,
  },
  journeyHeroCountry: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[100],
  },
  journeyHeroLevel: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[50],
    lineHeight: 22,
    marginBottom: 2,
  },
  journeyHeroHint: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[300],
    lineHeight: 20,
  },
  journeyNewHeroImage: {
    width: 56,
    height: 56,
  },
  flocksHeroButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.primary[600],
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: colors.primary[400],
  },
  flocksHeroImage: {
    width: 56,
    height: 56,
  },
  flocksHeroLogo: {
    width: 56,
    height: 56,
    borderRadius: 10,
  },
  flocksHeroText: {
    flex: 1,
    minWidth: 0,
  },
  flocksHeroTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[50],
    lineHeight: 22,
    marginBottom: 2,
  },
  flocksHeroHint: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[200],
    lineHeight: 20,
  },
  flocksHeroContinue: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[300],
  },
  ghostButton: {
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 8,
  },
  ghostButtonText: {
    color: colors.primary[500],
    fontSize: 16,
  },
  homeUpdateCard: {
    marginVertical: 12,
    marginBottom: 4,
  },
});
