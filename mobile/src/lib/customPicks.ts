import AsyncStorage from '@react-native-async-storage/async-storage';

/** Same key and shape as the web app's custom picks. Kept on the device only. */
export const CUSTOM_PICKS_STORAGE_KEY = 'birdr-custom-picks';
export const CUSTOM_PICK_MIN = 2;
export const CUSTOM_PICK_MAX = 6;

export type CustomPickSpecies = { id: number; name: string };
export type CustomPick = { key: string; species: CustomPickSpecies[] };

export function customPickKey(speciesIds: number[]): string {
  return [...speciesIds].sort((a, b) => a - b).join('-');
}

function isCustomPickSpecies(value: unknown): value is CustomPickSpecies {
  const row = value as CustomPickSpecies;
  return !!row && Number.isInteger(row.id) && typeof row.name === 'string';
}

/** Parse what was stored; anything malformed is dropped rather than crashing the screen. */
export function parseCustomPicks(raw: string | null | undefined): CustomPick[] {
  try {
    const parsed = JSON.parse(raw || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (pick): pick is { species: CustomPickSpecies[] } =>
          Array.isArray(pick?.species) &&
          pick.species.length >= CUSTOM_PICK_MIN &&
          pick.species.length <= CUSTOM_PICK_MAX &&
          pick.species.every(isCustomPickSpecies),
      )
      .map((pick) => ({ key: customPickKey(pick.species.map((s) => s.id)), species: pick.species }));
  } catch {
    return [];
  }
}

/** New pick first; the same birds in any order replace the older entry. */
export function withCustomPick(picks: CustomPick[], species: CustomPickSpecies[]): CustomPick[] {
  const key = customPickKey(species.map((s) => s.id));
  return [{ key, species }, ...picks.filter((pick) => pick.key !== key)];
}

export function withoutCustomPick(picks: CustomPick[], key: string): CustomPick[] {
  return picks.filter((pick) => pick.key !== key);
}

/** The pairs tab lists picks of two birds, the groups tab picks of three or more. */
export function customPicksForTab(picks: CustomPick[], tab: 'pairs' | 'flocks'): CustomPick[] {
  return picks.filter((pick) => (tab === 'pairs' ? pick.species.length === 2 : pick.species.length > 2));
}

export async function readCustomPicks(): Promise<CustomPick[]> {
  try {
    return parseCustomPicks(await AsyncStorage.getItem(CUSTOM_PICKS_STORAGE_KEY));
  } catch {
    return [];
  }
}

async function writeCustomPicks(picks: CustomPick[]): Promise<void> {
  try {
    await AsyncStorage.setItem(CUSTOM_PICKS_STORAGE_KEY, JSON.stringify(picks));
  } catch {
    /* ignore */
  }
}

export async function addCustomPick(species: CustomPickSpecies[]): Promise<CustomPick[]> {
  const next = withCustomPick(await readCustomPicks(), species);
  await writeCustomPicks(next);
  return next;
}

export async function removeCustomPick(key: string): Promise<CustomPick[]> {
  const next = withoutCustomPick(await readCustomPicks(), key);
  await writeCustomPicks(next);
  return next;
}
