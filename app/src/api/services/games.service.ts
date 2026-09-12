import axios from '../axios-config';
import { Game } from '../../core/app-context';
import { getApiBaseUrl } from '../baseUrl';

export interface PaginatedGamesResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Game[];
}

export interface QuestionWithAnswer {
  id: number;
  sequence: number;
  number: number;
  species: {
    name: string;
    name_latin: string;
    name_nl?: string;
    name_translated?: string;
    code: string;
    id: number;
    images?: Array<{ url: string; link?: string; contributor?: string }>;
    videos?: Array<{ url: string; link?: string; contributor?: string }>;
    sounds?: Array<{ url: string; link?: string; contributor?: string }>;
  };
  user_answer: {
    id: number;
    name: string;
    name_latin: string;
    name_nl?: string;
    name_translated?: string;
    code: string;
    images?: Array<{ url: string; link?: string; contributor?: string }>;
    videos?: Array<{ url: string; link?: string; contributor?: string }>;
    sounds?: Array<{ url: string; link?: string; contributor?: string }>;
  } | null;
  time_taken_seconds: number | null;
  points: number | null;
  correct: boolean | null;
  created: string;
  media_item?: {
    type: 'image' | 'video' | 'audio';
    url: string;
    link?: string;
    contributor?: string;
    source?: string;
  } | null;
}

export interface GameDetailWithAnswers {
  token: string;
  country: {
    code: string;
    name: string;
    count?: number;
  };
  level: string;
  language: string;
  created: string;
  multiplayer: boolean;
  length: number;
  progress: number;
  media: string;
  repeat: boolean;
  ended: boolean;
  tax_order?: string;
  tax_family?: string;
  species_group?: string;
  rarity: 'familiar' | 'regular' | 'exceptional';
  include_escapes: boolean;
  questions: QuestionWithAnswer[];
  total_score: number;
}

class GamesService {
  private get baseURL(): string {
    return getApiBaseUrl();
  }

  /**
   * Get paginated list of games played by the authenticated user
   */
  async getMyGames(page: number = 1): Promise<PaginatedGamesResponse> {
    try {
      const response = await axios.get<PaginatedGamesResponse>(
        `${this.baseURL}/api/my-games/`,
        {
          params: {
            page: page,
            _: Date.now(),
          },
          headers: {
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache',
            Pragma: 'no-cache',
          },
        }
      );
      return response.data;
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Get game details with all questions and user's answers.
   * With playerToken: public GET /api/games/<token>/with-answers/?player_token= (guests).
   * Without: GET /api/my-games/<token>/ (JWT).
   */
  async getGameDetail(
    token: string,
    options?: { playerToken?: string }
  ): Promise<GameDetailWithAnswers> {
    try {
      const pt = options?.playerToken;
      const url = pt
        ? `${this.baseURL}/api/games/${encodeURIComponent(token)}/with-answers/`
        : `${this.baseURL}/api/my-games/${encodeURIComponent(token)}/`;
      const params: Record<string, string | number> = { _: Date.now() };
      if (pt) params.player_token = pt;
      const response = await axios.get<GameDetailWithAnswers>(url, {
        params,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
          Pragma: 'no-cache',
        },
      });
      return response.data;
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  private handleError(error: any): Error {
    if (axios.isAxiosError(error) && error.response) {
      const message = error.response.data?.error || 
                     error.response.data?.detail || 
                     error.response.data?.message || 
                     'Failed to load games.';
      return new Error(message);
    }
    return new Error('An unexpected error occurred.');
  }
}

export const gamesService = new GamesService();

