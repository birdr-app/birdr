import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { DrawerContentComponentProps } from '@react-navigation/drawer';
import { colors } from '../theme';
import { getAppVersionDisplay } from '../utils/appVersion';

const MENU_ITEMS: { route: string; label: string }[] = [
  { route: 'Home', label: 'Home' },
  { route: 'Start', label: 'New game' },
  { route: 'Scores', label: 'High scores' },
  { route: 'CountryChallengeLeaderboard', label: 'Country leaderboard' },
  { route: 'Updates', label: 'Updates' },
  { route: 'Help', label: 'Community & help' },
  { route: 'Privacy', label: 'Privacy' },
  { route: 'About', label: 'About Birdr' },
];

export function LeftDrawerContent(props: DrawerContentComponentProps) {
  const { state, navigation } = props;
  const { version: appVersion, build: buildNumber, codename } = getAppVersionDisplay();
  const versionLine = (() => {
    const base = buildNumber ? `${appVersion} (${buildNumber})` : appVersion;
    return codename ? `${base} · ${codename}` : base;
  })();

  return (
    <View style={styles.container}>
      <View style={styles.menuHeader}>
        <Text style={styles.menuHeaderTitle}>Birdr</Text>
        <Text style={styles.menuHeaderVersion}>Version {versionLine}</Text>
      </View>
      <View style={styles.footerSpacer}>
        {MENU_ITEMS.map((item) => {
          const currentRoute = state.routes[state.index]?.name;
          const isHelpDetail =
            currentRoute === 'HelpDetail' &&
            (state.routes[state.index].params as { slug?: string } | undefined)?.slug;
          const focused =
            currentRoute === item.route ||
            (item.route === 'Privacy' && isHelpDetail === 'privacy') ||
            (item.route === 'About' && isHelpDetail === 'about');
          return (
            <TouchableOpacity
              key={item.route}
              style={[styles.item, focused && styles.itemFocused]}
              onPress={() => {
                if (item.route === 'Privacy') {
                  navigation.navigate('HelpDetail', { slug: 'privacy' });
                } else if (item.route === 'About') {
                  navigation.navigate('HelpDetail', { slug: 'about' });
                } else {
                  navigation.navigate(item.route);
                }
                navigation.closeDrawer();
              }}
            >
              <Text style={[styles.label, focused && styles.labelFocused]}>{item.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <View style={styles.footer}>
        <Text style={styles.footerText}>Data: eBird</Text>
        <Text style={styles.footerText}>Media: iNaturalist, Wikimedia, GBIF, EOL, Observation.org, Xeno-Canto</Text>
        <Text style={styles.footerText}>Developed by GoedLoek</Text>
        <Text style={styles.footerText}>Contact: info@goedloek.nl</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingTop: 56,
    paddingHorizontal: 16,
  },
  menuHeader: {
    marginBottom: 12,
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
  footerSpacer: {
    flex: 1,
  },
  footer: {
    paddingVertical: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.primary[200],
  },
  footerText: {
    fontSize: 12,
    color: colors.primary[600],
    marginBottom: 4,
  },
});
