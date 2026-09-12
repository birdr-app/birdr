import { apiUrl } from './config';
import { getAuthHeaders } from './auth';
import { readApiErrorMessage } from './apiError';
import type { Game } from './games';

export type TroubleSpotSpecies = {
  species_id: number;
  name: string;
  name_latin: string;
  name_nl?: string;
  name_translated?: string;
  times_shown: number;
  correctly_answered: number;
  wrongly_answered: number;
  correct_rate: number | null;
  error_rate: number | null;
  illustration_url?: string | null;
  code?: string;
  fixed?: boolean;
};

export type TroubleSpotPair = {
  low_id: number;
  high_id: number;
  total_wrong: number;
  when_low_was_target: number;
  when_high_was_target: number;
  low_name: string;
  high_name: string;
  low_name_translated?: string;
  high_name_translated?: string;
  low_name_latin: string;
  high_name_latin: string;
  low_name_nl?: string;
  high_name_nl?: string;
  low_code?: string;
  high_code?: string;
  low_illustration_url?: string | null;
  high_illustration_url?: string | null;
  fixed?: boolean;
};

export type TroubleSpotsResponse = {
  country_code: string | null;
  species: TroubleSpotSpecies[];
  pairs: TroubleSpotPair[];
};

export async function fetchTroubleSpots(
  countryCode?: string,
  language?: string | null,
): Promise<TroubleSpotsResponse> {
  const headers = await getAuthHeaders();
  const params = new URLSearchParams();
  if (countryCode?.trim()) params.set('country_code', countryCode.trim().toUpperCase());
  if (language?.trim()) params.set('language', language.trim());
  const qs = params.toString();
  const response = await fetch(
    `${apiUrl('/api/practice/trouble-spots/')}${qs ? `?${qs}` : ''}`,
    { headers: { Accept: 'application/json', ...headers } },
  );
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response));
  }
  return (await response.json()) as TroubleSpotsResponse;
}

export type TroubleSpotMixup = {
  pair: TroubleSpotPair;
  otherId: number;
  otherName: string;
  otherLatin: string;
  otherNl?: string;
  otherCode?: string;
  otherIllustrationUrl?: string | null;
  mixups: number;
};

export function mixupsForSpecies(
  speciesId: number,
  pairs: TroubleSpotPair[],
): TroubleSpotMixup[] {
  return pairs
    .filter((pair) => pair.low_id === speciesId || pair.high_id === speciesId)
    .map((pair) => {
      const otherIsLow = pair.high_id === speciesId;
      return {
        pair,
        otherId: otherIsLow ? pair.low_id : pair.high_id,
        otherName: otherIsLow
          ? (pair.low_name_translated || pair.low_name)
          : (pair.high_name_translated || pair.high_name),
        otherLatin: otherIsLow ? pair.low_name_latin : pair.high_name_latin,
        otherNl: otherIsLow ? pair.low_name_nl : pair.high_name_nl,
        otherCode: otherIsLow ? pair.low_code : pair.high_code,
        otherIllustrationUrl: otherIsLow ? pair.low_illustration_url : pair.high_illustration_url,
        mixups: pair.total_wrong,
      };
    })
    .sort((a, b) => b.mixups - a.mixups);
}

export type StartPairPracticeResponse = {
  game: Game;
  player_token: string;
};

export async function startConfusionPairPractice(
  lowId: number,
  highId: number,
  countryCode?: string,
): Promise<StartPairPracticeResponse> {
  const headers = await getAuthHeaders();
  const body: Record<string, unknown> = { low_id: lowId, high_id: highId };
  if (countryCode?.trim()) body.country_code = countryCode.trim().toUpperCase();
  const response = await fetch(apiUrl('/api/practice/confusion-pair/start/'), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response));
  }
  return (await response.json()) as StartPairPracticeResponse;
}

export async function startSpeciesPractice(
  speciesId: number,
  countryCode?: string,
): Promise<StartPairPracticeResponse> {
  const headers = await getAuthHeaders();
  const body: Record<string, unknown> = { species_id: speciesId };
  if (countryCode?.trim()) body.country_code = countryCode.trim().toUpperCase();
  const response = await fetch(apiUrl('/api/practice/species/start/'), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response));
  }
  return (await response.json()) as StartPairPracticeResponse;
}
