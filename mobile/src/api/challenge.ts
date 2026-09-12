import { apiUrl } from './config';
import { getAuthHeaders } from './auth';

export type PlayerRef = {
  id: number;
  token: string;
  name: string;
  language: string;
};

export type QuestionOption = {
  id: number;
  code: string;
  name: string;
  name_latin: string;
  name_nl?: string;
  name_translated?: string;
  images?: Array<{ url: string }>;
  sounds?: Array<{ url: string }>;
  videos?: Array<{ url: string }>;
};

export type ChallengeQuestion = {
  id: number;
  number: number;
  sequence: number;
  game: { token: string; speed_seconds?: number | null; level?: string; media?: string };
  options?: QuestionOption[];
  images: Array<{ id?: number; url: string; link?: string; contributor?: string; source?: string }>;
  sounds: Array<{ id?: number; url: string; link?: string; contributor?: string; source?: string }>;
  videos: Array<{ id?: number; url: string; link?: string; contributor?: string; source?: string }>;
};

export type AnswerPayload = {
  question_id: number;
  answer_id?: number;
  player_token: string;
  timed_out?: boolean;
};

/** Response from submitChallengeAnswer; backend AnswerSerializer returns answer, species, correct. */
export type SubmitChallengeAnswerResponse = {
  correct?: boolean;
  score?: number;
  answer?: QuestionOption;
  species?: QuestionOption;
  media_link?: string | null;
  [k: string]: unknown;
};

const CHALLENGE_PLAYER_KEY = 'challenge_player_token';

export async function getStoredChallengePlayerToken(): Promise<string | null> {
  const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
  return AsyncStorage.getItem(CHALLENGE_PLAYER_KEY);
}

export async function setStoredChallengePlayerToken(token: string): Promise<void> {
  const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
  await AsyncStorage.setItem(CHALLENGE_PLAYER_KEY, token);
}

export async function clearStoredChallengePlayerToken(): Promise<void> {
  const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
  await AsyncStorage.removeItem(CHALLENGE_PLAYER_KEY);
}

function playerAuthHeaders(playerToken: string): HeadersInit {
  return {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    Authorization: `Bearer ${playerToken}`,
  };
}

/** Create a player for journey play (links to user if JWT sent). */
export async function createChallengePlayer(
  name: string,
  language: string
): Promise<PlayerRef & { token: string }> {
  const headers = (await getAuthHeaders()) as Record<string, string>;
  const response = await fetch(apiUrl('/api/player/'), {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name.trim(), language }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Failed to create player';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to create player');
  }
  return data as PlayerRef & { token: string };
}

export async function getChallengeQuestion(
  gameToken: string,
  playerToken?: string | null,
  options?: { cacheBust?: boolean; timeoutMs?: number; signal?: AbortSignal }
): Promise<ChallengeQuestion | null> {
  const headers: HeadersInit = { Accept: 'application/json' };
  if (playerToken) {
    Object.assign(headers, playerAuthHeaders(playerToken));
  }
  const url =
    apiUrl(`/api/games/${gameToken}/question`) +
    (options?.cacheBust ? `?${Date.now()}` : '');
  const timeoutMs = options?.timeoutMs ?? 25_000;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const onExternalAbort = () => controller.abort();
  options?.signal?.addEventListener('abort', onExternalAbort);
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers,
      signal: controller.signal,
    });
    if (response.status === 404 || response.status === 204) return null;
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const msg = data.detail ?? data.error ?? data.message ?? 'Failed to load question';
      if (typeof msg === 'string') throw new Error(msg);
      if (Array.isArray(msg)) throw new Error(msg.join(', '));
      throw new Error('Failed to load question');
    }
    const question = data as ChallengeQuestion;
    if (question?.game?.token !== gameToken) {
      return null;
    }
    return question;
  } finally {
    clearTimeout(timeoutId);
    options?.signal?.removeEventListener('abort', onExternalAbort);
  }
}

export async function submitChallengeAnswer(
  payload: AnswerPayload,
  playerToken: string
): Promise<SubmitChallengeAnswerResponse> {
  const { ensureFreshAccessToken } = await import('./auth');
  const jwt = await ensureFreshAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  if (jwt) {
    headers.Authorization = `Bearer ${jwt}`;
  } else {
    Object.assign(headers, playerAuthHeaders(playerToken) as Record<string, string>);
  }
  const response = await fetch(apiUrl('/api/answer/'), {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Failed to submit answer';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to submit answer');
  }
  return data as SubmitChallengeAnswerResponse;
}
