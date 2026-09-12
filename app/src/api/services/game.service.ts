import { ApiClient } from '../client';
import { Game, Question, Species } from '../types';

export interface CreateGameRequest {
  multiplayer: boolean;
  country: string;
  language: string;
  level: string;
  length: string;
  media: string;
  tax_order?: string;
  tax_family?: string;
  species_group?: string;
  season?: string;
  rarity: 'familiar' | 'regular' | 'exceptional';
  include_escapes: boolean;
}

export interface GameService {
  createGame(data: CreateGameRequest, playerToken: string): Promise<Game>;
  loadGame(gameCode: string): Promise<Game>;
  getQuestion(gameToken: string): Promise<Question>;
}

export class GameServiceImpl implements GameService {
  constructor(private client: ApiClient) {}

  async createGame(data: CreateGameRequest, playerToken: string): Promise<Game> {
    return this.client.post<Game>('/api/games/', data, {
      headers: {
        'Authorization': `Token ${playerToken}`,
      },
    });
  }

  async loadGame(gameCode: string): Promise<Game> {
    return this.client.get<Game>(`/api/games/${gameCode}/`);
  }

  async getQuestion(gameToken: string): Promise<Question> {
    const hash = new Date().getTime();
    return this.client.get<Question>(`/api/games/${gameToken}/question?${hash}`);
  }
}

