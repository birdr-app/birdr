import React, { useEffect, useRef } from 'react';
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Pressable,
  ScrollView,
  Dimensions,
  Animated,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useMenu } from '../context/MenuContext';
import { useGameModes } from '../context/GameModesContext';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from '../i18n/TranslationContext';
import { COURSE_LOCALES } from '../api/course';
import { colors } from '../theme';
import { getAppVersionDisplay } from '../utils/appVersion';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const PANEL_WIDTH = Math.min(SCREEN_WIDTH * 0.85, 340);

/**
 * `advanced` items only show once the player has unlocked all game modes; `locales` items only in
 * those app languages (the beginners course is written in Dutch).
 */
const MENU_ITEMS: { route: string; labelKey: string; advanced?: boolean; locales?: string[]; beta?: boolean; divider?: boolean; small?: boolean }[] = [
  { route: 'Home', labelKey: 'home' },
  { route: 'Scores', labelKey: 'game_hiscores' },
  { route: 'Course', labelKey: 'course_title', locales: COURSE_LOCALES, beta: true },
  { route: 'TripList', labelKey: 'trip_title', beta: true },
  { route: 'CountryChallengeLeaderboard', labelKey: 'country_leaderboard', advanced: true },
  { route: 'LeagueList', labelKey: 'league_national', advanced: true },
  { route: 'SurvivalScores', labelKey: 'survival_highscores', advanced: true },
  { route: 'Updates', labelKey: 'updates', divider: true, small: true },
  { route: 'Help', labelKey: 'community_menu', small: true },
  { route: 'Privacy', labelKey: 'privacy', small: true },
  { route: 'About', labelKey: 'about_birdr', small: true },
];

export function LeftMenuModal() {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { t, locale } = useTranslation();
  const { leftMenuVisible, closeLeftMenu, currentRouteName } = useMenu();
  const { showMenuExtras } = useGameModes();
  const menuItems = MENU_ITEMS.filter(
    (item) => (showMenuExtras || !item.advanced) && (!item.locales || item.locales.includes(locale))
  );
  const slideAnim = useRef(new Animated.Value(-PANEL_WIDTH)).current;

  useEffect(() => {
    Animated.timing(slideAnim, {
      toValue: leftMenuVisible ? 0 : -PANEL_WIDTH,
      duration: 250,
      useNativeDriver: true,
    }).start();
  }, [leftMenuVisible, slideAnim]);

  const handleItem = (routeName: string) => {
    closeLeftMenu();
    if (routeName === 'Privacy') {
      (navigation as any).navigate('HelpDetail', { slug: 'privacy' });
    } else if (routeName === 'About') {
      (navigation as any).navigate('HelpDetail', { slug: 'about' });
    } else {
      (navigation as any).navigate(routeName);
    }
  };

  const currentRoute = currentRouteName;
  const { version: appVersion, build: buildNumber, codename } = getAppVersionDisplay();
  const versionLine = (() => {
    const base = `${t('version')} ${appVersion}`;
    return codename ? `${base} · ${codename}` : base;
  })();

  return (
    <Modal
      visible={leftMenuVisible}
      transparent
      animationType="none"
      onRequestClose={closeLeftMenu}
    >
      <View style={styles.container}>
        <Pressable style={styles.backdrop} onPress={closeLeftMenu} />
        <Animated.View
          style={[
            styles.panel,
            {
              width: PANEL_WIDTH,
              transform: [{ translateX: slideAnim }],
            },
          ]}
        >
          <View style={StyleSheet.absoluteFill}>
            <ScrollView
              style={styles.scroll}
              contentContainerStyle={[styles.content, { paddingTop: Math.max(24, insets.top) }]}
            >
              <View style={styles.menuHeader}>
                <Text style={styles.menuHeaderTitle}>Motmot</Text>
              </View>
              {menuItems.map((item) => {
                const isFocused =
                  currentRoute === item.route ||
                  (item.route === 'Help' && currentRoute === 'HelpDetail') ||
                  (item.route === 'LeagueList' && currentRoute?.startsWith('League')) ||
                  (item.route === 'TripList' && currentRoute?.startsWith('Trip')) ||
                  (item.route === 'Course' && currentRoute?.startsWith('Course'));
                const label = t(item.labelKey);
                return (
                  <React.Fragment key={item.route}>
                  {item.divider ? <View style={styles.divider} /> : null}
                  <TouchableOpacity
                    style={[styles.item, item.small && styles.itemSmall, isFocused && styles.itemFocused]}
                    onPress={() => handleItem(item.route)}
                    accessibilityRole="button"
                    accessibilityLabel={label}
                  >
                    <Text style={[styles.label, item.small && styles.labelSmall, isFocused && styles.labelFocused]}>
                      {label}
                      {item.beta ? <Text style={styles.beta}>{`  ${t('beta').toUpperCase()}`}</Text> : null}
                    </Text>
                  </TouchableOpacity>
                  </React.Fragment>
                );
              })}
              <View style={styles.footer}>
                <Text style={styles.footerText} accessibilityLabel={versionLine}>
                  {versionLine}
                </Text>
                <Text style={styles.footerText}>{t('data_ebird')}</Text>
                <Text style={styles.footerText}>{t('media_credits')}</Text>
                <Text style={styles.footerText}>{t('developed_by')}</Text>
                <Text style={styles.footerText}>{t('contact')}</Text>
              </View>
            </ScrollView>
          </View>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'flex-start',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  panel: {
    position: 'absolute',
    top: 0,
    left: 0,
    bottom: 0,
    backgroundColor: '#fff',
    shadowColor: '#000',
    shadowOffset: { width: 2, height: 0 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 8,
  },
  scroll: { flex: 1 },
  content: {
    paddingHorizontal: 24,
    paddingBottom: 32,
  },
  menuHeader: {
    marginBottom: 8,
    paddingBottom: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[200],
  },
  menuHeaderTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 6,
  },
  menuHeaderVersion: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[600],
  },
  item: {
    paddingVertical: 14,
    paddingHorizontal: 8,
  },
  itemSmall: { paddingVertical: 8 },
  labelSmall: { fontSize: 15 },
  itemFocused: {
    backgroundColor: colors.primary[100],
    borderRadius: 8,
  },
  divider: { height: 1, backgroundColor: colors.primary[200], marginVertical: 8, marginHorizontal: 16 },
  beta: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5, color: colors.primary[700] },
  label: {
    fontSize: 18,
    color: colors.primary[800],
  },
  labelFocused: {
    fontWeight: '600',
  },
  footer: {
    paddingVertical: 24,
    marginTop: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.primary[200],
  },
  footerText: {
    fontSize: 12,
    color: colors.primary[600],
    marginBottom: 4,
  },
});
