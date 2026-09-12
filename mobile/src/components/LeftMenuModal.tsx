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
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { getAppVersionDisplay } from '../utils/appVersion';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const PANEL_WIDTH = Math.min(SCREEN_WIDTH * 0.85, 340);

const MENU_ITEMS: { route: string; labelKey: string }[] = [
  { route: 'Home', labelKey: 'home' },
  { route: 'Start', labelKey: 'new_game' },
  { route: 'Scores', labelKey: 'high_scores' },
  { route: 'CountryChallengeLeaderboard', labelKey: 'country_leaderboard' },
  { route: 'Updates', labelKey: 'updates' },
  { route: 'Help', labelKey: 'community_menu' },
  { route: 'Privacy', labelKey: 'privacy' },
  { route: 'About', labelKey: 'about_birdr' },
];

export function LeftMenuModal() {
  const navigation = useNavigation();
  const insets = useSafeAreaInsets();
  const { t } = useTranslation();
  const { leftMenuVisible, closeLeftMenu, currentRouteName } = useMenu();
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
          <Pressable style={StyleSheet.absoluteFill} onPress={(e) => e.stopPropagation()}>
            <ScrollView
              style={styles.scroll}
              contentContainerStyle={[styles.content, { paddingTop: Math.max(24, insets.top) }]}
            >
              <View style={styles.menuHeader}>
                <Text style={styles.menuHeaderTitle}>Birdr</Text>
              </View>
              {MENU_ITEMS.map((item) => {
                const isFocused =
                  currentRoute === item.route ||
                  (item.route === 'Help' && currentRoute === 'HelpDetail');
                const label = t(item.labelKey);
                return (
                  <TouchableOpacity
                    key={item.route}
                    style={[styles.item, isFocused && styles.itemFocused]}
                    onPress={() => handleItem(item.route)}
                    accessibilityRole="button"
                    accessibilityLabel={label}
                  >
                    <Text style={[styles.label, isFocused && styles.labelFocused]}>{label}</Text>
                  </TouchableOpacity>
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
          </Pressable>
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
  itemFocused: {
    backgroundColor: colors.primary[100],
    borderRadius: 8,
  },
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
