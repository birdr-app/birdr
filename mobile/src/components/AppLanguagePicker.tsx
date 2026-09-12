import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { APP_LOCALES, APP_LOCALE_LABELS, isAppLocale, type AppLocale } from '../i18n/appLocales';
import { colors } from '../theme';

type AppLanguagePickerProps = {
  value: string;
  onChange: (locale: AppLocale) => void;
  variant?: 'chips' | 'menu';
};

function localeLabel(value: string): string {
  return isAppLocale(value) ? APP_LOCALE_LABELS[value] : APP_LOCALE_LABELS.en;
}

export function AppLanguagePicker({
  value,
  onChange,
  variant = 'chips',
}: AppLanguagePickerProps) {
  const [open, setOpen] = useState(false);
  const current = localeLabel(value);

  if (variant === 'menu') {
    return (
      <View>
        <TouchableOpacity
          style={styles.menuSummary}
          onPress={() => setOpen((currentOpen) => !currentOpen)}
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={`App language, ${current}`}
        >
          <View style={styles.menuLabelRow}>
            <Text style={styles.menuLabel}>App language</Text>
          </View>
          <Text style={styles.menuValue}>
            {current}
            <Text style={styles.menuChevron}>{open ? ' ▴' : ' ▾'}</Text>
          </Text>
        </TouchableOpacity>
        {open
          ? APP_LOCALES.map((locale) => {
              const selected = value === locale;
              return (
                <TouchableOpacity
                  key={locale}
                  style={styles.menuOption}
                  onPress={() => {
                    onChange(locale);
                    setOpen(false);
                  }}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                >
                  <Text style={[styles.menuOptionText, selected && styles.menuOptionSelected]}>
                    {APP_LOCALE_LABELS[locale]}
                  </Text>
                </TouchableOpacity>
              );
            })
          : null}
      </View>
    );
  }

  return (
    <View style={styles.chips}>
      {APP_LOCALES.map((locale) => {
        const selected = value === locale;
        return (
          <TouchableOpacity
            key={locale}
            style={[styles.chip, selected && styles.chipSelected]}
            onPress={() => onChange(locale)}
          >
            <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
              {APP_LOCALE_LABELS[locale]}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  menuSummary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingVertical: 2,
  },
  menuLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexShrink: 1,
  },
  menuLabel: {
    fontSize: 17,
    color: colors.primary[600],
  },
  menuValue: {
    fontSize: 17,
    color: colors.primary[800],
  },
  menuChevron: {
    fontSize: 17,
    color: colors.primary[400],
  },
  menuOption: {
    paddingVertical: 8,
    paddingLeft: 25,
  },
  menuOptionText: {
    fontSize: 17,
    color: colors.primary[600],
  },
  menuOptionSelected: {
    color: colors.primary[800],
    fontWeight: '600',
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.primary[300],
    backgroundColor: 'transparent',
  },
  chipSelected: {
    backgroundColor: colors.primary[500],
    borderColor: colors.primary[500],
  },
  chipText: {
    fontSize: 14,
    color: colors.primary[800],
  },
  chipTextSelected: {
    color: colors.primary[50],
    fontWeight: '600',
  },
});
