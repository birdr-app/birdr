import React, { useEffect, useRef, useState } from 'react';
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
  Image,
  BackHandler,
  Platform,
} from 'react-native';
import { exitApp } from '@logicwind/react-native-exit-app';
import { useNavigation } from '@react-navigation/native';
import { useMenu } from '../context/MenuContext';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { listBirdrJourneys } from '../api/birdrJourney';
import { listFlocks } from '../api/flocks';
import { useTranslation } from '../i18n/TranslationContext';
import { AppLanguagePicker } from './AppLanguagePicker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors } from '../theme';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const PANEL_WIDTH = Math.min(SCREEN_WIDTH * 0.85, 340);

const USER_MENU_ITEMS: { route: string; labelKey: string }[] = [
  { route: 'Checklist', labelKey: 'checklist_title' },
  { route: 'TroubleSpots', labelKey: 'trouble_spots' },
  { route: 'MyGames', labelKey: 'my_games' },
  { route: 'Settings', labelKey: 'profile' },
];

export function UserMenuModal() {
  const navigation = useNavigation();
  const { userMenuVisible, closeUserMenu } = useMenu();
  const { isAuthenticated, logout } = useAuth();
  const { profile, avatarUrl, initials } = useProfile();
  const { t, locale, setLocale } = useTranslation();
  const insets = useSafeAreaInsets();
  const slideAnim = useRef(new Animated.Value(PANEL_WIDTH)).current;
  const [hasFlocks, setHasFlocks] = useState(false);
  const [hasCountryChallenges, setHasCountryChallenges] = useState(false);

  useEffect(() => {
    Animated.timing(slideAnim, {
      toValue: userMenuVisible ? 0 : PANEL_WIDTH,
      duration: 250,
      useNativeDriver: true,
    }).start();
  }, [userMenuVisible, slideAnim]);

  useEffect(() => {
    if (!userMenuVisible) return;
    let cancelled = false;
    (async () => {
      if (isAuthenticated) {
        try {
          const flocks = await listFlocks();
          if (!cancelled) setHasFlocks(flocks.length > 0);
        } catch {
          if (!cancelled) setHasFlocks(false);
        }
      } else if (!cancelled) {
        setHasFlocks(false);
      }
      try {
        const journeys = await listBirdrJourneys();
        if (!cancelled) setHasCountryChallenges(journeys.length > 0);
      } catch {
        if (!cancelled) setHasCountryChallenges(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userMenuVisible, isAuthenticated]);

  const handleItem = (route: string) => {
    closeUserMenu();
    (navigation as any).navigate(route);
  };

  const handleExit = () => {
    closeUserMenu();
    requestAnimationFrame(() => {
      try {
        exitApp();
      } catch {
        if (Platform.OS === 'android') {
          BackHandler.exitApp();
        }
      }
    });
  };

  return (
    <Modal
      visible={userMenuVisible}
      transparent
      animationType="none"
      onRequestClose={closeUserMenu}
    >
      <View style={styles.container}>
        <Pressable style={styles.backdrop} onPress={closeUserMenu} />
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
            <ScrollView style={styles.scroll} contentContainerStyle={[styles.content, { paddingTop: Math.max(56, insets.top) }]}>
              <Text style={styles.sectionTitle}>{t('account')}</Text>
              <AppLanguagePicker
                variant="menu"
                value={locale}
                onChange={setLocale}
              />
              <View style={styles.separator} />
              {!isAuthenticated ? (
                <>
                  <TouchableOpacity style={styles.menuItem} onPress={() => handleItem('Login')}>
                    <Text style={styles.menuLabel}>{t('login')}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.menuItem} onPress={() => handleItem('Register')}>
                    <Text style={styles.menuLabel}>{t('register')}</Text>
                  </TouchableOpacity>
                  <View style={styles.separator} />
                  <Text style={styles.hint}>
                    {t('login_to_save_progress')}
                  </Text>
                </>
              ) : (
                <View style={styles.userSummary}>
                  <View style={styles.userAvatarWrap}>
                    {avatarUrl ? (
                      <Image source={{ uri: avatarUrl }} style={styles.userAvatar} resizeMode="cover" />
                    ) : (
                      <View style={styles.userInitialsCircle}>
                        <Text style={styles.userInitialsText}>{initials || '?'}</Text>
                      </View>
                    )}
                  </View>
                  <Text style={styles.userName} numberOfLines={1}>
                    {profile?.username || profile?.email || t('logged_in')}
                  </Text>
                  <Text style={styles.hint}>{t('you_are_logged_in')}</Text>
                </View>
              )}
              {hasFlocks && (
                <TouchableOpacity
                  style={styles.menuItem}
                  onPress={() => handleItem('FlockList')}
                >
                  <Text style={styles.menuLabel}>{t('flocks')}</Text>
                </TouchableOpacity>
              )}
              {hasCountryChallenges && (
                <TouchableOpacity
                  style={styles.menuItem}
                  onPress={() => handleItem('BirdrJourneyList')}
                >
                  <Text style={styles.menuLabel}>{t('country_challenges')}</Text>
                </TouchableOpacity>
              )}
              {USER_MENU_ITEMS.map((item) => (
                <TouchableOpacity
                  key={item.route}
                  style={styles.menuItem}
                  onPress={() => handleItem(item.route)}
                >
                  <Text style={styles.menuLabel}>{t(item.labelKey)}</Text>
                </TouchableOpacity>
              ))}
              <View style={styles.separator} />
              {isAuthenticated && (
                <TouchableOpacity
                  style={[styles.menuItem, styles.logout]}
                  onPress={async () => {
                    await logout();
                    closeUserMenu();
                    (navigation as any).navigate('Home');
                  }}
                >
                  <Text style={styles.logoutLabel}>{t('logout')}</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity
                style={[styles.menuItem, styles.exitItem]}
                onPress={handleExit}
              >
                <Text style={styles.exitLabel}>{t('close_app')}</Text>
              </TouchableOpacity>
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
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  panel: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#fff',
    shadowColor: '#000',
    shadowOffset: { width: -2, height: 0 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 8,
  },
  scroll: { flex: 1 },
  content: {
    paddingHorizontal: 24,
    paddingBottom: 32,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 16,
  },
  menuItem: {
    paddingVertical: 14,
  },
  menuLabel: {
    fontSize: 17,
    color: colors.primary[800],
  },
  logout: {
    marginTop: 8,
  },
  logoutLabel: {
    fontSize: 17,
    color: colors.error[500],
    fontWeight: '500',
  },
  exitItem: {
    marginTop: 8,
  },
  exitLabel: {
    fontSize: 17,
    color: colors.primary[600],
    fontWeight: '500',
  },
  separator: {
    height: 1,
    backgroundColor: colors.primary[200],
    marginVertical: 12,
  },
  hint: {
    fontSize: 14,
    color: colors.primary[600],
    marginBottom: 8,
  },
  userSummary: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 12,
  },
  userAvatarWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    overflow: 'hidden',
    backgroundColor: colors.primary[100],
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
  },
  userInitialsCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  userInitialsText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary[50],
  },
  userName: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary[800],
  },
  languageRow: {
    marginBottom: 4,
  },
  languageLabel: {
    fontSize: 14,
    color: colors.primary[600],
    marginBottom: 8,
  },
  languageChips: {
    flexDirection: 'row',
    gap: 10,
  },
  languageChip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.primary[300],
    backgroundColor: 'transparent',
  },
  languageChipSelected: {
    backgroundColor: colors.primary[500],
    borderColor: colors.primary[500],
  },
  languageChipText: {
    fontSize: 15,
    color: colors.primary[800],
  },
  languageChipTextSelected: {
    color: colors.primary[50],
    fontWeight: '600',
  },
});
