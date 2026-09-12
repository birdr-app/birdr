import React, { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useTranslation } from '../i18n/TranslationContext';
import { SpeciesViewButton } from './SpeciesViewButton';
import { ComparisonModal } from './ComparisonModal';

type Props = {
  species1Id?: number | null;
  species2Id?: number | null;
  species1Name?: string;
  species2Name?: string;
};

export function ComparisonButton({
  species1Id,
  species2Id,
  species1Name,
  species2Name,
}: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  if (!species1Id || !species2Id || species1Id === species2Id) return null;

  return (
    <View style={styles.wrap}>
      <SpeciesViewButton
        label={t('view_comparison')}
        onPress={(e) => {
          e?.stopPropagation?.();
          setOpen(true);
        }}
        variant="compare"
        badge={t('beta')}
        testID="comparison.open"
        accessibilityLabel={`${t('view_comparison')} (${t('beta')})`}
      />
      <ComparisonModal
        visible={open}
        onClose={() => setOpen(false)}
        species1Id={species1Id}
        species2Id={species2Id}
        species1Name={species1Name}
        species2Name={species2Name}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { width: '100%' },
});
