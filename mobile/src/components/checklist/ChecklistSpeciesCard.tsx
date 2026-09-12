import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import type { ChecklistSpecies } from '../../api/checklist';
import { colors } from '../../theme';
import { CachedRemoteImage } from '../CachedRemoteImage';
import {
  frequencyLabel,
  isMega,
  isVeryRare,
  speciesDisplayName,
  statsLine,
} from './checklistUtils';

const IMAGE_SIZE = 56;

type Props = {
  species: ChecklistSpecies;
  onPress: () => void;
  t: (key: string, fallback?: string) => string;
};

export function ChecklistSpeciesCard({ species, onPress, t }: Props) {
  const rarity = frequencyLabel(species.frequency, t);
  const dimmed = species.status === 'unseen' || species.status === 'missed';
  const statusLabel =
    species.status === 'identified'
      ? t('checklist_status_seen', 'Seen')
      : species.status === 'missed'
        ? t('checklist_status_missed', 'Missed')
        : t('checklist_status_unseen', 'Unseen');

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.85}>
      <Text style={styles.name} numberOfLines={1}>
        {speciesDisplayName(species)}
      </Text>

      <View style={styles.row}>
        <View style={[styles.imageWrap, dimmed && styles.imageDimmed]}>
          {species.illustration_url ? (
            <CachedRemoteImage
              source={{ uri: species.illustration_url }}
              style={styles.image}
              contentFit="cover"
              recyclingKey={species.illustration_url}
            />
          ) : (
            <View style={styles.silhouette}>
              <Text style={styles.silhouetteIcon}>🐦</Text>
            </View>
          )}
        </View>

        <View style={styles.rightCol}>
          <View
            style={[
              styles.statusPill,
              species.status === 'identified' && styles.statusSeen,
              species.status === 'missed' && styles.statusMissed,
            ]}
          >
            <Text
              style={[
                styles.statusPillText,
                species.status === 'missed' && styles.statusMissedText,
              ]}
            >
              {statusLabel}
            </Text>
          </View>
          <Text style={styles.detail} numberOfLines={2}>
            {statsLine(species, t)}
          </Text>
          {rarity ? (
            <Text
              style={[
                styles.rarity,
                (isVeryRare(species.frequency) || isMega(species.frequency)) &&
                  styles.rarityVeryRare,
                isMega(species.frequency) && styles.rarityMega,
              ]}
              numberOfLines={1}
            >
              {rarity}
            </Text>
          ) : null}
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    marginHorizontal: 12,
    marginVertical: 3,
    borderWidth: 1,
    borderColor: colors.primary[100],
  },
  name: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.primary[900],
    marginBottom: 6,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  imageWrap: {
    width: IMAGE_SIZE,
    height: IMAGE_SIZE,
    borderRadius: 6,
    overflow: 'hidden',
    backgroundColor: colors.primary[50],
  },
  imageDimmed: { opacity: 0.45 },
  image: {
    width: IMAGE_SIZE,
    height: IMAGE_SIZE,
  },
  silhouette: {
    width: IMAGE_SIZE,
    height: IMAGE_SIZE,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.primary[100],
  },
  silhouetteIcon: { fontSize: 22, opacity: 0.45 },
  rightCol: {
    flex: 1,
    marginLeft: 10,
    alignItems: 'flex-end',
    justifyContent: 'center',
    gap: 3,
  },
  statusPill: {
    backgroundColor: colors.primary[100],
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  statusSeen: { backgroundColor: colors.success[50] },
  statusMissed: { backgroundColor: colors.error[500] },
  statusPillText: { fontSize: 10, fontWeight: '700', color: colors.primary[800] },
  statusMissedText: { color: '#fff' },
  detail: {
    fontSize: 10,
    color: colors.primary[600],
    textAlign: 'right',
    lineHeight: 14,
  },
  rarity: {
    fontSize: 9,
    fontWeight: '600',
    color: colors.primary[500],
    textAlign: 'right',
  },
  rarityVeryRare: { color: '#b8860b' },
  rarityMega: { fontWeight: '800', color: '#b45309' },
});
