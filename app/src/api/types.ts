// API Types - Centralized type definitions
export interface Country {
  code: string;
  name: string;
  count?: number;
  parent?: string | null;
  kind?: string;
  hemisphere?: string;
}

export interface Language {
  code: string;
  name: string;
}

export interface TaxOrder {
  tax_order: string;
  tax_order_en: string;
  count: number;
}

export interface TaxFamily {
  tax_family: string;
  tax_family_en: string;
  count: number;
}

export interface SpeciesGroup {
  species_group: string;
  name_en: string;
  name_nl: string;
  name_es?: string;
  name_fr?: string;
  name_de?: string;
  name_it?: string;
  name_pt_br?: string;
  name_ja?: string;
  count: number;
}

export interface Player {
  id?: number;
  name: string;
  token: string;
  language: string;
}

export interface Species {
  id: number;
  name: string;
  name_nl?: string;
  name_latin?: string;
  code: string;
  images: Array<{ url: string }>;
}

export interface Question {
  id: number;
  sequence?: number;
  species?: Species;
  options?: Species[];
}

export interface Answer {
  id?: number;
  question?: Question;
  answer?: Species;
  player?: Player;
  correct?: boolean;
}

export interface Game {
  id?: number;
  token: string;
  host?: Player;
  length?: number;
}

export interface MultiPlayer {
  name: string;
  score: number;
  token: string;
}

export interface Score {
  id?: number;
  player?: Player;
  game?: Game;
  score: number;
}

export interface Update {
  id: number;
  message: string;
  created_at: string;
}

