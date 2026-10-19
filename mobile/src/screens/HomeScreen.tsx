import React, { useCallback, useState, useEffect, useMemo, useRef } from 'react';
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
import { getFlockImage, getStartGameImage, getSurvivalImage } from '../constants/birdrFlockImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { useGameModes } from '../context/GameModesContext';
import { modeVisibility } from '../game/gameModes';
import { FeedbackForm } from '../components/FeedbackForm';
import { useSoftUpdateAvailable } from '../hooks/useSoftUpdateAvailable';
import { resolveMediaUrl } from '../api/config';
import { fetchLeague, fetchLeagueOverview, pickMainLeague, type LeagueCountry, type LeagueDetail } from '../api/league';
import { leagueFlag } from '../lib/league';
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
  SurvivalStart: undefined;
  SurvivalScores: { countryCode?: string } | undefined;
  League: { countryCode?: string } | undefined;
};

function ModeTile({
  label,
  art,
  tileStyle,
  onPress,
  testID,
}: {
  label: string;
  art: React.ReactNode;
  tileStyle: object;
  onPress: () => void;
  testID: string;
}) {
  return (
    <TouchableOpacity
      style={[styles.modeTile, tileStyle]}
      onPress={onPress}
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      {art}
      <Text style={styles.modeTileLabel} numberOfLines={2}>
        {label}
      </Text>
    </TouchableOpacity>
  );
}

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
  const [leagueDetail, setLeagueDetail] = useState<LeagueDetail | null>(null);
  const [leagueSuggested, setLeagueSuggested] = useState<LeagueCountry | null>(null);
  const [leagueLoaded, setLeagueLoaded] = useState(false);
  const gameModes = useGameModes();

  const loadLeagueSummary = useCallback(async () => {
    try {
      const overview = await fetchLeagueOverview();
      const joined = (await pickMainLeague(overview.memberships))?.country;
      if (joined) {
        setLeagueSuggested(null);
        setLeagueDetail(await fetchLeague(joined.code));
      } else {
        setLeagueDetail(null);
        setLeagueSuggested(overview.suggested[0] ?? null);
      }
    } catch {
      setLeagueDetail(null);
      setLeagueSuggested(null);
    } finally {
      setLeagueLoaded(true);
    }
  }, []);

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
      void loadLeagueSummary();
    }, [loadActiveJourney, loadFlockSummary, loadLeagueSummary, locale])
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

  const leagueToday = leagueDetail?.today;
  const needsCountdown =
    (!!flockChallenge && flockChallenge.status === 'active' && !flockChallenge.my_completed) ||
    (!!leagueToday && !leagueToday.played);

  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    if (!needsCountdown) return undefined;
    const id = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, [needsCountdown, flockChallenge?.id, flockChallenge?.ends_at]);

  const leagueCountry = leagueDetail?.country ?? leagueSuggested;
  const leagueCountryLabel = leagueCountry ? getCountryDisplayName(leagueCountry, locale) : '';
  const leagueTitle = leagueCountry
    ? `${leagueFlag(leagueCountry.code)} ${t('league_title_country', { country: leagueCountryLabel })}`.trim()
    : t('league');
  const leagueStatusLine = useMemo(() => {
    if (!leagueToday) {
      return leagueSuggested ? t('league_home_join_cta') : t('league_home_hint');
    }
    if (leagueToday.my_result) {
      const rank = leagueToday.my_result.rank;
      return rank
        ? t('league_home_played_rank', { score: leagueToday.my_result.score, rank })
        : t('league_points', { score: leagueToday.my_result.score });
    }
    const remaining = getChallengeTimeRemaining(leagueToday.closes_at, new Date(nowTick));
    return remaining
      ? t('league_home_play_now', { time: formatChallengeCountdown(remaining) })
      : t('league_home_hint');
  }, [leagueToday, leagueSuggested, nowTick, t]);

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

  const modes = modeVisibility({
    gamesPlayed: gameModes.gamesPlayed,
    showAll: gameModes.showAll,
    inLeague: !!leagueDetail,
    inFlock: !!mainFlock,
    hasJourney: !!activeJourney,
    playedSurvival: gameModes.playedSurvival,
    isAuthenticated,
    unlockSeen: gameModes.unlockSeen,
  });
  const modesLoading = !gameModes.ready || !leagueLoaded || (flocksLoading && !flocksReady);
  const showUnlockBanner = gameModes.ready && modes.showUnlockBanner;

  // The unlock banner is a one-time moment: once seen, leaving home counts as dismissing it.
  const unlockBannerShownRef = useRef(false);
  unlockBannerShownRef.current = showUnlockBanner;
  const { markUnlockSeen } = gameModes;
  useFocusEffect(
    useCallback(
      () => () => {
        if (unlockBannerShownRef.current) markUnlockSeen();
      },
      [markUnlockSeen]
    )
  );

  const survivalCard = (
    <TouchableOpacity
      style={styles.survivalHeroButton}
      onPress={() => navigation.navigate('SurvivalStart')}
      testID="home.survival"
      accessibilityLabel={`${t('survival')}, ${t('survival_home_hint')}`}
    >
      <GameArtImage source={getSurvivalImage(visualStyle)} style={styles.journeyNewHeroImage} resizeMode="contain" />
      <View style={styles.journeyHeroText}>
        <Text style={styles.journeyHeroLevel} numberOfLines={2}>
          {t('survival')}
        </Text>
        <Text style={styles.survivalHeroHint} numberOfLines={2}>
          {t('survival_home_hint')}
        </Text>
      </View>
    </TouchableOpacity>
  );

  const goLeague = () =>
    navigation.navigate('League', leagueCountry ? { countryCode: leagueCountry.code } : undefined);

  const leagueCard = (
    <TouchableOpacity
      style={styles.leagueHeroButton}
      onPress={goLeague}
      testID="home.league"
      accessibilityLabel={`${leagueTitle}, ${leagueStatusLine}`}
    >
      <Text style={styles.leagueHeroEmoji}>{leagueToday?.played ? '⭐' : '🏆'}</Text>
      <View style={styles.journeyHeroText}>
        <Text style={styles.journeyHeroLevel} numberOfLines={2}>
          {leagueTitle}
        </Text>
        <Text style={styles.survivalHeroHint} numberOfLines={2}>
          {leagueStatusLine}
        </Text>
      </View>
    </TouchableOpacity>
  );

  const flockCard = mainFlock ? (
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
      <GameArtImage source={getFlockImage('invite', visualStyle)} style={styles.flocksHeroImage} resizeMode="contain" />
      <View style={styles.flocksHeroText}>
        <Text style={styles.flocksHeroTitle} numberOfLines={2}>
          {t('flocks_start')}
        </Text>
        <Text style={styles.flocksHeroHint} numberOfLines={2}>
          {t('flocks_home_start_cta')}
        </Text>
      </View>
    </TouchableOpacity>
  );

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
      {showUnlockBanner && (
        <View style={styles.unlockBanner} testID="home.modesUnlocked">
          <Text style={styles.unlockBannerText}>{t('game_modes_unlocked')}</Text>
          <TouchableOpacity
            onPress={markUnlockSeen}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            accessibilityRole="button"
            accessibilityLabel={t('close')}
          >
            <Text style={styles.unlockBannerClose}>✕</Text>
          </TouchableOpacity>
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

        {modesLoading ? (
          <View style={styles.secondaryLoadingWrap}>
            <ActivityIndicator size="small" color={colors.primary[500]} />
          </View>
        ) : (
          <>
            {modes.survival === 'full' && survivalCard}
            {modes.league === 'full' && leagueCard}
            {modes.flock === 'full' && flockCard}
            {modes.hasTiles && (
              <View style={styles.moreModes}>
                <Text style={styles.moreModesTitle}>{t('more_ways_to_play')}</Text>
                <View style={styles.modeTileRow}>
                  {modes.survival === 'tile' && (
                    <ModeTile
                      testID="home.survivalTile"
                      label={t('survival')}
                      tileStyle={styles.survivalTile}
                      art={<GameArtImage source={getSurvivalImage(visualStyle)} style={styles.modeTileImage} resizeMode="contain" />}
                      onPress={() => navigation.navigate('SurvivalStart')}
                    />
                  )}
                  {modes.league === 'tile' && (
                    <ModeTile
                      testID="home.leagueTile"
                      label={t('league')}
                      tileStyle={styles.leagueTile}
                      art={<Text style={styles.modeTileEmoji}>🏆</Text>}
                      onPress={goLeague}
                    />
                  )}
                  {modes.flock === 'tile' && (
                    <ModeTile
                      testID="home.flocksTile"
                      label={t('flocks_start')}
                      tileStyle={styles.flocksTile}
                      art={<GameArtImage source={getFlockImage('invite', visualStyle)} style={styles.modeTileImage} resizeMode="contain" />}
                      onPress={() => void goFlocks()}
                    />
                  )}
                </View>
                {modes.stage === 'beginner' && (
                  <TouchableOpacity
                    style={styles.showAllLink}
                    onPress={() => gameModes.setShowAll(true)}
                    testID="home.showAllModes"
                    accessibilityRole="button"
                  >
                    <Text style={styles.showAllLinkText}>{t('show_all_game_modes')}</Text>
                  </TouchableOpacity>
                )}
              </View>
            )}
          </>
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
  survivalHeroButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.primary[700],
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: colors.primary[400],
  },
  leagueHeroButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.primary[900],
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#f59e0b',
  },
  leagueHeroEmoji: {
    width: 56,
    fontSize: 40,
    textAlign: 'center',
  },
  survivalHeroHint: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[200],
    lineHeight: 20,
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
  unlockBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#fef3c7',
    borderWidth: 1,
    borderColor: '#f59e0b',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  unlockBannerText: {
    flex: 1,
    fontSize: 15,
    fontWeight: '600',
    color: '#78350f',
    lineHeight: 20,
  },
  unlockBannerClose: {
    fontSize: 16,
    fontWeight: '700',
    color: '#92400e',
  },
  moreModes: {
    width: '100%',
    marginTop: 4,
  },
  moreModesTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.primary[700],
    marginBottom: 8,
  },
  modeTileRow: {
    flexDirection: 'row',
    gap: 10,
  },
  modeTile: {
    flex: 1,
    alignItems: 'center',
    gap: 6,
    paddingVertical: 12,
    paddingHorizontal: 6,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.primary[400],
  },
  survivalTile: {
    backgroundColor: colors.primary[700],
  },
  leagueTile: {
    backgroundColor: colors.primary[900],
    borderColor: '#f59e0b',
  },
  flocksTile: {
    backgroundColor: colors.primary[600],
  },
  modeTileImage: {
    width: 40,
    height: 40,
  },
  modeTileEmoji: {
    fontSize: 30,
    lineHeight: 40,
    textAlign: 'center',
  },
  modeTileLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.primary[50],
    textAlign: 'center',
  },
  showAllLink: {
    alignSelf: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginTop: 4,
  },
  showAllLinkText: {
    color: colors.primary[600],
    fontSize: 15,
    fontWeight: '600',
    textDecorationLine: 'underline',
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
