import axios from './axios-config';
import type { Game } from '../core/app-context';

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
  const params: Record<string, string> = {};
  if (countryCode?.trim()) params.country_code = countryCode.trim().toUpperCase();
  if (language?.trim()) params.language = language.trim();
  const { data } = await axios.get<TroubleSpotsResponse>('/api/practice/trouble-spots/', { params });
  return data;
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
  const body: Record<string, unknown> = { low_id: lowId, high_id: highId };
  if (countryCode?.trim()) body.country_code = countryCode.trim().toUpperCase();
  const { data } = await axios.post<StartPairPracticeResponse>(
    '/api/practice/confusion-pair/start/',
    body,
  );
  return data;
}

export async function startSpeciesPractice(
  speciesId: number,
  countryCode?: string,
): Promise<StartPairPracticeResponse> {
  const body: Record<string, unknown> = { species_id: speciesId };
  if (countryCode?.trim()) body.country_code = countryCode.trim().toUpperCase();
  const { data } = await axios.post<StartPairPracticeResponse>(
    '/api/practice/species/start/',
    body,
  );
  return data;
}
