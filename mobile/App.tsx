import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer } from '@react-navigation/native';
import { navigationRef } from './src/navigation/navigationRef';
import { setupNotificationResponseHandler } from './src/lib/notifications';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { Platform } from 'react-native';
import { AutocompleteDropdownContextProvider } from 'react-native-autocomplete-dropdown';
import { MenuProvider } from './src/context/MenuContext';
import { GameProvider } from './src/context/GameContext';
import { GameWebSocketProvider } from './src/context/GameWebSocketContext';
import { AuthProvider } from './src/context/AuthContext';
import { ProfileProvider } from './src/context/ProfileContext';
import { VisualStyleProvider } from './src/context/VisualStyleContext';
import { TranslationProvider } from './src/i18n/TranslationContext';
import { DeepLinkHandler } from './src/components/DeepLinkHandler';
import AppNavigator from './src/navigation/AppNavigator';
import { AppVersionGate } from './src/components/AppVersionGate';
import { GOOGLE_WEB_CLIENT_ID, GOOGLE_IOS_CLIENT_ID } from './src/api/config';
import { installAppIdentityFetch } from './src/api/installAppIdentityFetch';
import { trackScreenView } from './src/api/analytics';
import { subscribeMemoryReleaseOnBackground } from './src/lib/releaseMemory';

installAppIdentityFetch();

export default function App() {
  useEffect(() => {
    return setupNotificationResponseHandler();
  }, []);

  useEffect(() => subscribeMemoryReleaseOnBackground(), []);

  useEffect(() => {
    const webClientId = GOOGLE_WEB_CLIENT_ID?.trim() || undefined;
    GoogleSignin.configure({
      webClientId: webClientId ?? undefined,
      ...(Platform.OS === 'ios' && GOOGLE_IOS_CLIENT_ID
        ? { iosClientId: GOOGLE_IOS_CLIENT_ID.trim() }
        : {}),
      offlineAccess: !!webClientId,
    });
  }, []);

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <NavigationContainer
        ref={navigationRef}
        onStateChange={() => {
          const route = navigationRef.getCurrentRoute();
          if (route?.name) {
            trackScreenView(`/mobile/${route.name}`);
          }
        }}
      >
        <AutocompleteDropdownContextProvider>
        <AuthProvider>
          <ProfileProvider>
            <VisualStyleProvider>
            <GameProvider>
              <TranslationProvider>
                <GameWebSocketProvider>
                  <DeepLinkHandler>
                    <MenuProvider>
                      <AppVersionGate>
                        <AppNavigator />
                      </AppVersionGate>
                    </MenuProvider>
                  </DeepLinkHandler>
                </GameWebSocketProvider>
              </TranslationProvider>
            </GameProvider>
            </VisualStyleProvider>
          </ProfileProvider>
        </AuthProvider>
        </AutocompleteDropdownContextProvider>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
