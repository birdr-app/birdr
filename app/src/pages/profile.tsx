import React, { useState, useEffect, useContext } from "react";
import {
  Box,
  Button,
  VStack,
  HStack,
  Input,
  Text,
  Heading,
  Avatar,
  Container,
  Field,
  Alert,
  AlertIndicator,
  Spinner,
  Link,
  Switch,
  Flex,
  Image,
} from "@chakra-ui/react";
import { FormattedMessage, useIntl } from "react-intl";
import { useNavigate } from "react-router-dom";
import { profileService, UserProfile, ProfileUpdateData, getAvatarUrl } from "../api/services/profile.service";
import { authService } from "../api/services/auth.service";
import { Page } from "../shared/components/layout";
import { UseCountries } from "../user/use-countries";
import { UseLanguages } from "../user/use-languages";
import { ProfileLanguageSelect } from "../components/profile-language-select";
import { ProfileCountrySelect } from "../components/profile-country-select";
import { AppLanguageSelect } from "../components/app-language-select";
import type { AppLocale } from "../i18n/app-locales";
import { speciesLanguageFromAppLocale } from "../i18n/app-locales";
import AppContext from "../core/app-context";
import { useAuthProfile } from "../core/auth-profile-context";
import { parseVisualStyle, type VisualStyle } from "../user/visual-style";

export const ProfilePage = () => {
  const navigate = useNavigate();
  const intl = useIntl();
  const { setAppLanguage: persistAppLanguage, applySpeciesLanguage, visualStyle: contextVisualStyle, setVisualStyle } = useContext(AppContext);
  const { applyProfile } = useAuthProfile();
  const { countries } = UseCountries();
  const { languages } = UseLanguages();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [receiveUpdates, setReceiveUpdates] = useState(false);
  const [language, setLanguage] = useState("en");
  const [appLanguage, setAppLanguage] = useState<AppLocale>("en");
  const [timezone, setTimezone] = useState("Europe/Amsterdam");
  const [countryCode, setCountryCode] = useState<string | null>(null);
  const [visualStyle, setVisualStyleLocal] = useState<VisualStyle>(contextVisualStyle ?? "classic");

  useEffect(() => {
    const loadProfile = async () => {
      if (!authService.getAccessToken()) {
        navigate("/login");
        return;
      }

      try {
        setLoading(true);
        const profileData = await profileService.getProfile();
        setProfile(profileData);
        setUsername(profileData.username);
        setFirstName(profileData.first_name || "");
        setLastName(profileData.last_name || "");
        setAvatarPreview(getAvatarUrl(profileData));
        setReceiveUpdates(profileData.receive_updates ?? true);
        setLanguage(profileData.language || "en");
        setAppLanguage((profileData.app_language as AppLocale) || "en");
        setTimezone(profileData.timezone || "Europe/Amsterdam");
        setCountryCode(profileData.country_code || null);
        setVisualStyleLocal(parseVisualStyle(profileData.visual_style));
      } catch (err: any) {
        setError(err.message || "Failed to load profile");
        if (err.message?.includes("401") || err.message?.includes("Unauthorized")) {
          authService.clearTokens();
          navigate("/login");
        }
      } finally {
        setLoading(false);
      }
    };

    loadProfile();
  }, [navigate]);

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAvatarFile(file);
      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);

    try {
      const updateData: ProfileUpdateData = {};
      
      if (username !== profile?.username) {
        updateData.username = username;
      }
      
      if (firstName !== (profile?.first_name || "")) {
        updateData.first_name = firstName;
      }
      
      if (lastName !== (profile?.last_name || "")) {
        updateData.last_name = lastName;
      }
      
      if (avatarFile) {
        updateData.avatar = avatarFile;
      } else if (!avatarPreview && profile?.avatar_url) {
        // Avatar was removed (preview is null/empty but profile had an avatar)
        updateData.avatar = null;
      }

      if (receiveUpdates !== (profile?.receive_updates ?? true)) {
        updateData.receive_updates = receiveUpdates;
      }

      if (language !== (profile?.language || "en")) {
        updateData.language = language;
      }

      if (appLanguage !== (profile?.app_language || "")) {
        updateData.app_language = appLanguage;
      }

      if (countryCode !== (profile?.country_code || null)) {
        updateData.country_code = countryCode;
      }

      if (timezone !== (profile?.timezone ?? "Europe/Amsterdam")) {
        updateData.timezone = timezone?.trim() || "Europe/Amsterdam";
      }

      if (visualStyle !== parseVisualStyle(profile?.visual_style)) {
        updateData.visual_style = visualStyle;
      }

      if (Object.keys(updateData).length === 0) {
        setSuccess("No changes to save");
        setSaving(false);
        return;
      }

      const updatedProfile = await profileService.updateProfile(updateData);
      setProfile(updatedProfile);
      applyProfile(updatedProfile);
      if (updateData.app_language) {
        persistAppLanguage?.(updatedProfile.app_language || appLanguage, {
          syncSpeciesLanguage: false,
        });
      }
      if (updateData.language || updateData.app_language) {
        applySpeciesLanguage?.(updatedProfile.language || language);
      }
      setUsername(updatedProfile.username);
      setFirstName(updatedProfile.first_name || "");
      setLastName(updatedProfile.last_name || "");
      setAvatarPreview(getAvatarUrl(updatedProfile));
      setAvatarFile(null);
      setReceiveUpdates(updatedProfile.receive_updates ?? true);
      setLanguage(updatedProfile.language || "en");
      setAppLanguage((updatedProfile.app_language as AppLocale) || "en");
      setTimezone(updatedProfile.timezone ?? "Europe/Amsterdam");
      setCountryCode(updatedProfile.country_code || null);
      setVisualStyleLocal(parseVisualStyle(updatedProfile.visual_style));
      setVisualStyle?.(parseVisualStyle(updatedProfile.visual_style));
      setSuccess("Profile updated successfully!");
      
      // Refresh auth state to update username in token if changed
      if (updateData.username) {
        window.location.reload();
      }
    } catch (err: any) {
      setError(err.message || "Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Page>
        <Page.Header>
          <Heading color={'gray.800'} size={'lg'} m={0}>
            <FormattedMessage id="profile" defaultMessage="Profile" />
          </Heading>
        </Page.Header>
        <Page.Body>
          <VStack gap={4}>
            <Spinner size="xl" colorPalette="primary" />
            <Text><FormattedMessage id="loading profile" defaultMessage="Loading profile..." /></Text>
          </VStack>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <Heading color={'gray.800'} size={'lg'} m={0}>
          <FormattedMessage id="profile" defaultMessage="Profile" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="md" py={8}>
          <VStack gap={6} align="stretch">

        {error && (
          <Alert.Root status="error">
            <AlertIndicator />
            <Alert.Content>
              <Alert.Title>{error}</Alert.Title>
            </Alert.Content>
          </Alert.Root>
        )}

        {success && (
          <Alert.Root status="info">
            <AlertIndicator />
            <Alert.Content>
              <Alert.Title>{success}</Alert.Title>
            </Alert.Content>
          </Alert.Root>
        )}

        <Box as="form" onSubmit={handleSubmit}>
          <VStack gap={6} align="stretch">
            {/* Avatar Section */}
            <VStack gap={4}>
              <Avatar.Root size="2xl" style={{ width: '120px', height: '120px' }}>
                {avatarPreview ? (
                  <Avatar.Image src={avatarPreview} alt={username || "User"} />
                ) : null}
                <Avatar.Fallback>
                  {(username || "User").charAt(0).toUpperCase()}
                </Avatar.Fallback>
              </Avatar.Root>
              
              <Box position="relative">
                <Input
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarChange}
                  display="none"
                  id="avatar-upload"
                />
                <Link
                  as="button"
                  type="button"
                  colorPalette="primary"
                  textDecoration="underline"
                  cursor="pointer"
                  onClick={() => document.getElementById('avatar-upload')?.click()}
                >
                  <FormattedMessage id="change_avatar" defaultMessage="Change Avatar" />
                </Link>
              </Box>
            </VStack>

            {/* Player Name Field */}
            <Field.Root>
              <Field.Label>
                <FormattedMessage id="player_name" defaultMessage="Player name" />
              </Field.Label>
              <Input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={intl.formatMessage({ id: 'placeholder enter player name', defaultMessage: 'Enter your player name' })}
                required
              />
            </Field.Root>

            {/* First Name Field */}
            <Field.Root>
              <Field.Label>
                <FormattedMessage id="first_name" defaultMessage="First Name" />
              </Field.Label>
              <Input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder={intl.formatMessage({ id: 'placeholder enter first name', defaultMessage: 'Enter your first name' })}
              />
            </Field.Root>

            {/* Last Name Field */}
            <Field.Root>
              <Field.Label>
                <FormattedMessage id="last_name" defaultMessage="Last Name" />
              </Field.Label>
              <Input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder={intl.formatMessage({ id: 'placeholder enter last name', defaultMessage: 'Enter your last name' })}
              />
            </Field.Root>

            {/* Email (read-only) */}
            <Field.Root>
              <Field.Label>
                <FormattedMessage id="email" defaultMessage="Email" />
              </Field.Label>
              <Input
                type="email"
                value={profile?.email || ""}
                disabled
                bg="gray.50"
              />
              <Text fontSize="sm" color="gray.500">
                <FormattedMessage 
                  id="email_cannot_be_changed" 
                  defaultMessage="Email cannot be changed" 
                />
              </Text>
            </Field.Root>

            <Field.Root>
              <Flex justify="space-between" align="center">
                <Box>
                  <Field.Label mb={0}>
                    <FormattedMessage
                      id="receive_updates"
                      defaultMessage="Receive Birdr updates by email"
                    />
                  </Field.Label>
                  <Text fontSize="sm" color="gray.500">
                    <FormattedMessage
                      id="receive_updates_hint"
                      defaultMessage="News and product updates from Birdr."
                    />
                  </Text>
                </Box>
                <Switch.Root
                  checked={receiveUpdates}
                  onCheckedChange={(e: { checked: boolean }) => setReceiveUpdates(e.checked === true)}
                  colorPalette="primary"
                >
                  <Switch.HiddenInput />
                  <Switch.Control />
                </Switch.Root>
              </Flex>
            </Field.Root>

            <Field.Root>
              <Field.Label>
                <FormattedMessage
                  id="visual_style"
                  defaultMessage="Game illustrations"
                />
              </Field.Label>
              <HStack
                gap={2}
                mt={2}
                align="stretch"
                role="radiogroup"
                aria-label={intl.formatMessage({
                  id: "visual_style",
                  defaultMessage: "Game illustrations",
                })}
              >
                {([
                  { id: "classic" as const, src: "/images/birdr-start-game.png", labelId: "visual_style_bertie", labelDefault: "Bertie" },
                  { id: "stylish" as const, src: "/images/stylish/birdr-start-game.png?v=2", labelId: "visual_style_classic", labelDefault: "Classic" },
                  { id: "none" as const, src: null, labelId: "visual_style_none", labelDefault: "None" },
                ]).map((option) => {
                  const selected = visualStyle === option.id;
                  return (
                    <Box key={option.id} flex={1} minW={0} aspectRatio="1">
                      <Button
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        w="100%"
                        h="100%"
                        p={2}
                        variant="outline"
                        borderWidth="2px"
                        borderRadius="md"
                        css={{ borderRadius: '8px' }}
                        borderColor={selected ? "primary.500" : "gray.200"}
                        bg={selected ? "primary.50" : "white"}
                        overflow="hidden"
                        onClick={() => {
                          setVisualStyleLocal(option.id);
                          setVisualStyle?.(option.id);
                        }}
                      >
                        <VStack gap={1} w="100%" h="100%" justify="center">
                          {option.src ? (
                            <Image
                              src={option.src}
                              alt=""
                              w="80%"
                              maxH="70%"
                              objectFit="contain"
                            />
                          ) : (
                            <Box
                              w="80%"
                              aspectRatio="1"
                              maxH="70%"
                              borderRadius="xl"
                              bg="primary.100"
                            />
                          )}
                          <Text fontWeight="600" fontSize="sm" color="primary.800">
                            <FormattedMessage id={option.labelId} defaultMessage={option.labelDefault} />
                          </Text>
                        </VStack>
                      </Button>
                    </Box>
                  );
                })}
              </HStack>
            </Field.Root>

            {/* App language vs bird names */}
            <Box>
              <Text fontSize="sm" fontWeight="medium" mb={1}>
                <FormattedMessage id="app_language" defaultMessage="App language" />
              </Text>
              <Text fontSize="sm" color="gray.500" mb={2}>
                <FormattedMessage id="app_language_hint" defaultMessage="Menus and buttons" />
              </Text>
              <AppLanguageSelect
                value={appLanguage}
                onChange={(locale) => {
                  setAppLanguage(locale);
                  setLanguage(speciesLanguageFromAppLocale(locale));
                }}
              />
            </Box>

            <Box>
              <Text fontSize="sm" fontWeight="medium" mb={1}>
                <FormattedMessage id="bird_name_language" defaultMessage="Bird name language" />
              </Text>
              <Text fontSize="sm" color="gray.500" mb={2}>
                <FormattedMessage
                  id="bird_name_language_hint"
                  defaultMessage="Names in quizzes and lists"
                />
              </Text>
              <ProfileLanguageSelect
                languages={languages}
                value={language}
                onChange={setLanguage}
              />
            </Box>

            {/* Country Preference */}
            <Box>
              <Text fontSize="sm" fontWeight="medium" mb={2}>
                <FormattedMessage id="preferred_country" defaultMessage="Preferred Country" />
              </Text>
              <ProfileCountrySelect
                countries={countries.filter((c) => !c.code.includes('NL-NH'))}
                value={countryCode}
                onChange={setCountryCode}
              />
            </Box>

            <Field.Root>
              <Field.Label>
                <FormattedMessage id="timezone" defaultMessage="Timezone" />
              </Field.Label>
              <Input
                type="text"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="e.g. Europe/Amsterdam"
              />
            </Field.Root>

            {/* Submit Button */}
            <Button
              type="submit"
              colorPalette="primary"
              width="full"
              loading={saving}
              loadingText={intl.formatMessage({ id: 'saving', defaultMessage: 'Saving...' })}
            >
              <FormattedMessage id="save_changes" defaultMessage="Save Changes" />
            </Button>
          </VStack>
        </Box>
          </VStack>
        </Container>
      </Page.Body>
    </Page>
  );
};

export default ProfilePage;

