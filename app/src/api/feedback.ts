import { apiUrl } from './baseUrl';
import { authService } from './services/auth.service';

/**
 * Send a comment to /api/feedback/: it is stored and mailed to the team. The signed-in user and the
 * local player are attached when there are any. Returns whether it was saved.
 */
export async function postFeedback(comment: string): Promise<boolean> {
  const player_token = localStorage.getItem('player-token');
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const accessToken = authService.getAccessToken();
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  try {
    const response = await fetch(apiUrl('/api/feedback/'), {
      method: 'POST',
      headers,
      body: JSON.stringify({ comment: comment.trim(), ...(player_token ? { player_token } : {}) }),
    });
    return response.ok;
  } catch {
    return false;
  }
}

/** The comment a Trip prep country request sends: easy to spot among other feedback. */
export function tripRequestComment(country: string, note: string, lang: string): string {
  const lines = [`Trip prep request: ${country.trim()}`];
  if (note.trim()) lines.push('', note.trim());
  lines.push('', `(app language: ${lang})`);
  return lines.join('\n');
}
