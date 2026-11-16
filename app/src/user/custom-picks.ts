export const CUSTOM_PICKS_STORAGE_KEY = 'birdr-custom-picks'
export const CUSTOM_PICK_MIN = 2
export const CUSTOM_PICK_MAX = 6

export type CustomPickSpecies = { id: number; name: string }

export type CustomPick = {
  key: string
  species: CustomPickSpecies[]
}

export function customPickKey(speciesIds: number[]): string {
  return [...speciesIds].sort((a, b) => a - b).join('-')
}

function isCustomPickSpecies(value: unknown): value is CustomPickSpecies {
  const row = value as CustomPickSpecies
  return !!row && Number.isInteger(row.id) && typeof row.name === 'string'
}

export function readCustomPicks(): CustomPick[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(CUSTOM_PICKS_STORAGE_KEY) || '[]')
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (pick): pick is { species: CustomPickSpecies[] } =>
          Array.isArray(pick?.species) &&
          pick.species.length >= CUSTOM_PICK_MIN &&
          pick.species.length <= CUSTOM_PICK_MAX &&
          pick.species.every(isCustomPickSpecies),
      )
      .map((pick) => ({ key: customPickKey(pick.species.map((s) => s.id)), species: pick.species }))
  } catch {
    return []
  }
}

function writeCustomPicks(picks: CustomPick[]): void {
  try {
    localStorage.setItem(CUSTOM_PICKS_STORAGE_KEY, JSON.stringify(picks))
  } catch {
    /* ignore */
  }
}

export function addCustomPick(species: CustomPickSpecies[]): CustomPick[] {
  const key = customPickKey(species.map((s) => s.id))
  const rest = readCustomPicks().filter((pick) => pick.key !== key)
  const next = [{ key, species }, ...rest]
  writeCustomPicks(next)
  return next
}

export function removeCustomPick(key: string): CustomPick[] {
  const next = readCustomPicks().filter((pick) => pick.key !== key)
  writeCustomPicks(next)
  return next
}
