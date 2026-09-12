/**
 * Types for MPG (multiplayer game) flow - aligned with React app / backend.
 */
export type SpeciesImage = { id?: number; url: string; link?: string; contributor?: string; source?: string };
export type SpeciesVideo = { id?: number; url: string; link?: string; contributor?: string; source?: string };
export type SpeciesSound = { id?: number; url: string; link?: string; contributor?: string; source?: string };

export type Species = {
  id: number;
  code?: string;
  name?: string;
  name_nl?: string;
  name_latin?: string;
  name_translated?: string;
  images?: SpeciesImage[];
  videos?: SpeciesVideo[];
  sounds?: SpeciesSound[];
  [key: string]: unknown;
};

export type GameRef = { token: string; media?: string; level?: string };

export type Question = {
  id: number;
  number: number;
  sequence: number;
  done?: boolean;
  /** Effective media for this question when mixed (flock Club Mix). */
  media?: string;
  game: GameRef;
  options?: Species[];
  images: SpeciesImage[];
  sounds: SpeciesSound[];
  videos: SpeciesVideo[];
};

export type Answer = {
  question?: Question;
  sequence?: number;
  answer?: Species;
  species?: Species;
  species_frequency?: string | null;
  media_link?: string | null;
  player?: { id: number; name: string; token: string };
  correct?: boolean;
  score?: number;
  [key: string]: unknown;
};

export type MultiPlayer = {
  id: number;
  name: string;
  is_host?: boolean;
  language?: string;
  status?: 'waiting' | 'correct' | 'incorrect';
  score?: number;
  ranking?: number;
  last_answer?: Answer;
};
