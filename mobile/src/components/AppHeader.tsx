import React from 'react';
import { View, Text, Image, TouchableOpacity, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { useMenu } from '../context/MenuContext';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

type AppHeaderProps = {
  title: string;
  routeName?: string;
  /** Shown left of the menu button, e.g. a back arrow. */
  leftExtra?: React.ReactNode;
};

export function AppHeader({ title, routeName, leftExtra }: AppHeaderProps) {
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, undefined>, string>>();
  const { t } = useTranslation();
  const { openUserMenu, openLeftMenu, setCurrentRouteName } = useMenu();
  const { isAuthenticated } = useAuth();
  const { avatarUrl, initials } = useProfile();
  const insets = useSafeAreaInsets();

  React.useEffect(() => {
    if (routeName) setCurrentRouteName(routeName);
  }, [routeName, setCurrentRouteName]);

  const renderUserIcon = () => {
    if (!isAuthenticated) {
      return <FontAwesome5 name="user" solid={false} size={20} color={colors.primary[800]} />;
    }
    if (avatarUrl) {
      return (
        <View style={styles.avatarWrap}>
          <Image source={{ uri: avatarUrl }} style={styles.avatar} resizeMode="cover" />
        </View>
      );
    }
    return (
      <View style={styles.initialsCircle}>
        <Text style={styles.initialsText}>{initials}</Text>
      </View>
    );
  };

  return (
    <View style={[styles.container, { paddingTop: Math.max(12, insets.top) }]}>
      <TouchableOpacity
        style={styles.sideButton}
        onPress={openLeftMenu}
        hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        accessibilityLabel={t('open_menu')}
      >
        <FontAwesome5 name="bars" solid={false} size={20} color={colors.primary[800]} />
      </TouchableOpacity>
      {leftExtra}
      <View style={styles.center}>
        <Text style={styles.title} numberOfLines={1}>
          {title}
        </Text>
      </View>
      <TouchableOpacity
        style={styles.sideButton}
        onPress={openUserMenu}
        hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
      >
        {renderUserIcon()}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    paddingBottom: 12,
    backgroundColor: colors.secondary[200],
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.secondary[300],
  },
  sideButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.primary[800],
  },
  icon: {
    fontSize: 22,
    color: colors.primary[800],
  },
  avatarWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: colors.primary[100],
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary[100],
  },
  initialsCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  initialsText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#fff',
  },
});
