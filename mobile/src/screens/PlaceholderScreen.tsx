import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

type PlaceholderScreenProps = {
  route: { params?: { title?: string }; name: string };
};

const SCREEN_TITLES: Record<string, string> = {
  Start: 'New game',
  Scores: 'High scores',
  Challenge: 'Country challenge',
  Updates: 'Updates',
  Help: 'Community',
  MyGames: 'My Games',
  Settings: 'Profile',
  MediaReview: 'Review media',
  Login: 'Login',
  Register: 'Register',
};

export function PlaceholderScreen({ route }: PlaceholderScreenProps) {
  const title = SCREEN_TITLES[route.name] || route.name;

  return (
    <View style={styles.container}>
      <Text style={styles.text}>{title}</Text>
      <Text style={styles.subtext}>Screen coming soon</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 24,
  },
  text: {
    fontSize: 20,
    fontWeight: '600',
    color: '#1a202c',
    marginBottom: 8,
  },
  subtext: {
    fontSize: 16,
    color: '#718096',
  },
});
