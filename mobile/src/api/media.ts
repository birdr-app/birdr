import { apiUrl } from './config';
import { getAuthHeaders } from './auth';

export type ReviewLevel = 'fast' | 'full' | 'thorough';

export type MediaReviewType = 'approved' | 'rejected' | 'not_sure';

export interface MediaMachinePrediction {
  predicted_review_type: 'approved' | 'rejected';
  confidence: number | null;
  model_version: string;
  features_version?: string | null;
}

export interface MediaItem {
  id: number;
  type: 'image' | 'video' | 'audio';
  source: string;
  url: string;
  link?: string | null;
  contributor?: string | null;
  species_name: string;
  species_code: string;
  species_id: number;
  hide: boolean;
  created: string;
  review_type?: MediaReviewType | null;
  machine_prediction?: MediaMachinePrediction | null;
  machine_human_agreement?: 'agree' | 'disagree' | null;
}

export interface PaginatedMediaResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: MediaItem[];
}

/** Species with its media embedded (GET /api/media-review-species/). */
export interface SpeciesWithMedia {
  id: number;
  name: string;
  total_media: number;
  unreviewed: number;
  approved: number;
  rejected: number;
  not_sure: number;
  media: MediaItem[];
}

export interface PaginatedSpeciesWithMediaResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: SpeciesWithMedia[];
}

export interface SpeciesReviewStats {
  id: number;
  name: string;
  total_media: number;
  unreviewed: number;
  approved: number;
  rejected: number;
  not_sure: number;
}

export interface SpeciesReviewStatsResponse {
  summary: {
    total_species: number;
    not_reviewed: number;
    partly_reviewed: number;
    reviewed: number;
    fully_reviewed: number;
  };
  species: SpeciesReviewStats[];
}

export async function getMedia(
  type: 'image' | 'video' | 'audio' = 'image',
  page: number = 1,
  countryCode?: string,
  language?: string,
  speciesId?: number,
  level: ReviewLevel = 'fast'
): Promise<PaginatedMediaResponse> {
  let url = `${apiUrl('/api/media/')}?type=${type}&page=${page}&level=${level}`;
  if (countryCode) url += `&country=${encodeURIComponent(countryCode)}`;
  if (language) url += `&language=${encodeURIComponent(language)}`;
  if (speciesId != null) url += `&species=${speciesId}`;
  const headers = await getAuthHeaders();
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error('Failed to load media');
  return response.json();
}

export async function getMediaReviewSpecies(
  type: 'image' | 'video' | 'audio' = 'image',
  page: number = 1,
  countryCode?: string,
  language?: string,
  speciesId?: number,
  level: ReviewLevel = 'fast'
): Promise<PaginatedSpeciesWithMediaResponse> {
  const params = new URLSearchParams({ type, page: String(page), level });
  if (countryCode) params.set('country', countryCode);
  if (language) params.set('language', language);
  if (speciesId != null) params.set('species', String(speciesId));
  const headers = await getAuthHeaders();
  const response = await fetch(apiUrl(`/api/media-review-species/?${params.toString()}`), { headers });
  if (!response.ok) throw new Error('Failed to load media');
  return response.json();
}

export async function reviewMedia(
  mediaId: number,
  playerToken: string | undefined,
  reviewType: 'approved' | 'rejected' | 'not_sure',
  description?: string
): Promise<void> {
  const body: Record<string, unknown> = {
    media_id: mediaId,
    review_type: reviewType,
    description: description || '',
  };
  if (playerToken != null) body.player_token = playerToken;
  const headers = await getAuthHeaders();
  const response = await fetch(apiUrl('/api/review-media/'), {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error('Failed to review media');
}

/** Image-only first assertion (approved or rejected). */
export async function reviewMediaFirstAssertion(
  mediaId: number,
  playerToken: string | undefined,
  reviewType: 'approved' | 'rejected',
  description?: string
): Promise<void> {
  const body: Record<string, unknown> = {
    media_id: mediaId,
    review_type: reviewType,
    description: description || '',
  };
  if (playerToken != null) body.player_token = playerToken;
  const headers = await getAuthHeaders();
  const response = await fetch(apiUrl('/api/review-media/first-assertion/'), {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error('Failed to review media');
}

export async function getSpeciesReviewStats(
  countryCode?: string,
  mediaType: string = 'image',
  language?: string
): Promise<SpeciesReviewStatsResponse> {
  const params = new URLSearchParams({ type: mediaType });
  if (countryCode) params.set('country', countryCode);
  if (language) params.set('language', language);
  const url = apiUrl(`/api/species-review-stats/?${params.toString()}`);
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to load species stats');
  return response.json();
}
