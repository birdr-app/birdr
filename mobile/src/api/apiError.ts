function messageText(value: unknown): string | null {
  if (typeof value === 'string') return value || null;
  if (Array.isArray(value)) {
    const parts = value.filter((x) => typeof x === 'string' && x);
    return parts.length ? parts.join(' ') : null;
  }
  return null;
}

/** Extract a user-visible message from a failed API response body. */
export function formatApiDetail(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null;
  const d = data as Record<string, unknown>;
  for (const key of ['detail', 'error', 'message', 'non_field_errors']) {
    const text = messageText(d[key]);
    if (text) return text;
  }
  // DRF field errors: {"country_code": ["Country is required ..."]}
  for (const value of Object.values(d)) {
    const text = messageText(value);
    if (text) return text;
  }
  return null;
}

export async function readApiErrorMessage(
  response: Response,
  fallback = 'Request failed'
): Promise<string> {
  if (response.status === 404) {
    return (
      'Checklist is not available on this server (404). ' +
      'Deploy the latest API or set EXPO_PUBLIC_API_URL to your dev backend.'
    );
  }
  if (response.status === 401) {
    return 'Session expired. Please sign in again.';
  }
  const data = await response.json().catch(() => null);
  return formatApiDetail(data) ?? `${fallback} (${response.status})`;
}
