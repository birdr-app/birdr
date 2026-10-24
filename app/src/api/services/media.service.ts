import { ApiClient } from '../client';

export type ReviewLevel = 'fast' | 'full' | 'thorough';

/** not_sure is being phased out; mystery counts as rejected in game play for now. */
export type ReviewType = 'approved' | 'rejected' | 'not_sure' | 'mystery';

export interface MediaItemReviewStatus {
  approved: number;
  rejected: number;
  dont_know: number;
}

export interface MediaItem {
  id: number;
  type: 'image' | 'video' | 'audio';
  source: string;
  url: string;
  link?: string | null;
  contributor?: string | null;
  copyright_text?: string | null;
  copyright_standardized?: string | null;
  non_commercial_only?: boolean;
  species_name: string;
  species_code: string;
  species_id: number;
  hide: boolean;
  created: string;
  /** Present when level=thorough */
  review_status?: MediaItemReviewStatus | null;
  /** Present when loaded via media-review-species: single review type for this item */
  review_type?: ReviewType | null;
  /** Offline ML first assertion (from MediaPrediction); null if absent */
  machine_prediction?: {
    predicted_review_type: 'approved' | 'rejected';
    confidence: number | null;
    model_version: string;
    features_version?: string | null;
  } | null;
  /** Compares latest human effective label to machine prediction */
  machine_human_agreement?: 'agree' | 'disagree' | null;
}

export interface PaginatedMediaResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: MediaItem[];
}

/** Species with all its media embedded (from media-review-species API). */
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

export interface MediaService {
  getMedia(type?: string, page?: number, countryCode?: string, language?: string, speciesId?: number, level?: ReviewLevel): Promise<PaginatedMediaResponse>;
  /** Species paginated by 3, each with all media embedded. Same filters as getMedia. */
  getMediaReviewSpecies(type?: string, page?: number, countryCode?: string, language?: string, speciesId?: number, level?: ReviewLevel): Promise<PaginatedSpeciesWithMediaResponse>;
  /** Pass playerToken when using a game player; omit when authenticated as a user (JWT). */
  reviewMedia(mediaId: number, playerToken: string | undefined, reviewType: ReviewType, description?: string): Promise<unknown>;
  /** Image-only first assertion (approved/rejected). Same auth as reviewMedia. */
  reviewMediaFirstAssertion(mediaId: number, playerToken: string | undefined, reviewType: 'approved' | 'rejected', description?: string): Promise<unknown>;
  getSpeciesReviewStats(countryCode?: string, mediaType?: string, language?: string): Promise<SpeciesReviewStatsResponse>;
}

export class MediaServiceImpl implements MediaService {
  constructor(private client: ApiClient) {}

  async getMedia(type: string = 'image', page: number = 1, countryCode?: string, language?: string, speciesId?: number, level: ReviewLevel = 'fast'): Promise<PaginatedMediaResponse> {
    let url = `/api/media/?type=${type}&page=${page}&level=${level}`;
    if (countryCode) {
      url += `&country=${countryCode}`;
    }
    if (language) {
      url += `&language=${encodeURIComponent(language)}`;
    }
    if (speciesId != null) {
      url += `&species=${speciesId}`;
    }
    const response = await this.client.get<PaginatedMediaResponse>(url);
    return response;
  }

  async getMediaReviewSpecies(type: string = 'image', page: number = 1, countryCode?: string, language?: string, speciesId?: number, level: ReviewLevel = 'fast'): Promise<PaginatedSpeciesWithMediaResponse> {
    const params = new URLSearchParams({ type, page: String(page), level });
    if (countryCode) params.set('country', countryCode);
    if (language) params.set('language', language);
    if (speciesId != null) params.set('species', String(speciesId));
    return this.client.get<PaginatedSpeciesWithMediaResponse>(`/api/media-review-species/?${params.toString()}`);
  }

  async reviewMedia(mediaId: number, playerToken: string | undefined, reviewType: ReviewType, description?: string): Promise<unknown> {
    const body: Record<string, unknown> = {
      media_id: mediaId,
      review_type: reviewType,
      description: description || '',
    };
    if (playerToken != null) {
      body.player_token = playerToken;
    }
    return this.client.post('/api/review-media/', body);
  }

  async reviewMediaFirstAssertion(
    mediaId: number,
    playerToken: string | undefined,
    reviewType: 'approved' | 'rejected',
    description?: string
  ): Promise<unknown> {
    const body: Record<string, unknown> = {
      media_id: mediaId,
      review_type: reviewType,
      description: description || '',
    };
    if (playerToken != null) {
      body.player_token = playerToken;
    }
    return this.client.post('/api/review-media/first-assertion/', body);
  }

  async getSpeciesReviewStats(countryCode?: string, mediaType: string = 'image', language?: string): Promise<SpeciesReviewStatsResponse> {
    const params = new URLSearchParams({ type: mediaType });
    if (countryCode) params.set('country', countryCode);
    if (language) params.set('language', language);
    return this.client.get<SpeciesReviewStatsResponse>(`/api/species-review-stats/?${params.toString()}`);
  }
}

