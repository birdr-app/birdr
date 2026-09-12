import { apiUrl } from './config';
import { getAuthHeaders } from './auth';

export type SpeciesComparison = {
  id: number;
  comparison_type: string;
  species_1: { id: number; name: string; name_latin: string };
  species_2: { id: number; name: string; name_latin: string };
  species_1_name: string;
  species_1_latin: string;
  species_1_code: string;
  species_2_name: string;
  species_2_latin: string;
  species_2_code: string;
  summary: string;
  summary_html?: string;
  detailed_comparison?: string;
  detailed_comparison_html?: string;
  size_comparison?: string;
  size_comparison_html?: string;
  plumage_comparison?: string;
  plumage_comparison_html?: string;
  behavior_comparison?: string;
  behavior_comparison_html?: string;
  habitat_comparison?: string;
  habitat_comparison_html?: string;
  vocalization_comparison?: string;
  vocalization_comparison_html?: string;
  identification_tips?: string;
  identification_tips_html?: string;
  generated_at: string;
  ai_model: string;
};

/**
 * Request or fetch a comparison between two species.
 * POST /api/compare/request/ (React app uses anonymous; add getAuthHeaders() here if backend requires auth).
 */
export async function requestComparison(
  species1Id: number,
  species2Id: number,
  language?: string,
): Promise<SpeciesComparison> {
  const params = new URLSearchParams();
  if (language) {
    params.set('app_language', language);
    params.set('language', language);
  }
  const query = params.toString();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (language) headers['Accept-Language'] = language;
  const response = await fetch(apiUrl(`/api/compare/request/${query ? `?${query}` : ''}`), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      comparison_type: 'species',
      species_1_id: species1Id,
      species_2_id: species2Id,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Failed to generate comparison';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to generate comparison');
  }
  return data as SpeciesComparison;
}

export async function submitCommunityComparison(
  species1Id: number,
  species2Id: number,
  summary: string,
): Promise<void> {
  const headers = await getAuthHeaders();
  const response = await fetch(apiUrl('/api/compare/community/'), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      species_1_id: species1Id,
      species_2_id: species2Id,
      summary,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Could not save your description';
    throw new Error(typeof msg === 'string' ? msg : 'Could not save your description');
  }
}
