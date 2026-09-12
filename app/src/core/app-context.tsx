import {createContext, Dispatch, SetStateAction} from 'react';
import { useState } from 'react';
import { TaxOrder } from '../user/use-tax-order';
import {TaxFamily} from "../user/use-tax-family"
import { type SpeciesGroup } from "../user/use-species-group"


export type Country = {
  code: string
  name: string
  count?: number
  parent?: string | null
  kind?: string
  hemisphere?: string
}

export type Language = {
  code: string
  name: string
}

export type Game = {
  token: string
  level: string
  created: string
  country: Country
  language: string
  question: Question
  length: number
  progress: number
  media: string
  repeat: boolean
  ended?: boolean
  host?: Player
  tax_order?: string
  tax_family?: string
  species_group?: string
  season?: string | null
  current_highscore?: Player
  rarity: 'familiar' | 'regular' | 'exceptional'
  include_escapes: boolean
  scores: Player[]
  user_score?: number
  correct_count?: number
  total_questions?: number
  game_type?: string
  pair_species_low_id?: number | null
  pair_species_high_id?: number | null
  pair_species_low_name?: string | null
  pair_species_high_name?: string | null
  pair_species_low_code?: string | null
  pair_species_high_code?: string | null
  pair_species_low_illustration_url?: string | null
  pair_species_high_illustration_url?: string | null
  focus_species_id?: number | null
  focus_species_name?: string | null
  focus_species_code?: string | null
  focus_species_illustration_url?: string | null
}

export type SpeciesImage = {
  id?: number;
  url: string;
  link?: string
  contributor?: string
  source?: string
}

export type SpeciesVideo = {
  id?: number;
  url: string;
  link?: string
  contributor?: string
  source?: string
}

export type SpeciesSound = {
  id?: number;
  url: string;
  link?: string
  contributor?: string
  source?: string
}

export type Species = {
  id: number
  code: string
  name: string
  name_nl: string
  name_latin: string
  name_translated: string
  tax_order: string
  tax_family: string
  tax_family_en: string
  images: SpeciesImage[]
  sounds: SpeciesSound[]
  videos: SpeciesVideo[]
  illustration_url?: string | null
  illustration_status?: string
  correct?: boolean
}


export type Question = {
  id: number
  number: number
  sequence: number
  done?: boolean
  /** Effective media for this question when mixed (flock Club Mix). */
  media?: string
  game: Game
  options?: Species[]
  images: SpeciesImage[]
  sounds: SpeciesSound[]
  videos: SpeciesVideo[]

}

export type Player = {
  id: number
  token: string
  name: string
  is_host?: boolean
  language: string
  score?: number
  last_answer?: Answer
  answers: Answer[]
}

export type MultiPlayer = {
  id: number
  name: string
  is_host?: boolean
  language?: string
  status?: 'waiting' | 'correct' | 'incorrect'
  score?: number
  ranking?: number
  last_answer?: Answer
}


export type Answer = {
  question?: Question
  sequence?: number
  answer?: Species
  species?: Species
  species_frequency?: string | null
  checklist_added?: boolean
  checklist_missed?: boolean
  player?: Player
  error?: number
  number?: number
  correct?: boolean
  score?: number
}


export type Score = {
  name: string
  ranking: number
  score: number
  created: Date
  level: string
  country: Country
  media: string
  length: number
  rarity?: string
  is_mine?: boolean
}


export type Reaction = {
  created?: Date
  message: string
  name?: string
  update_id: string
  player_token: string
}

export type User = {
  username: string
  first_name: string
  last_name: string
}


export type Update = {
  id: string
  created: Date
  message: string
  title: string
  user: User
  reactions: Reaction[]
}

type SharedState = {
  playerName?: string
  setPlayerName?: Dispatch<SetStateAction<string | undefined>>
  player?: Player
  createPlayer: () => Promise<Player | undefined>
  rarity: 'familiar' | 'regular' | 'exceptional'
  setRarity: Dispatch<SetStateAction<'familiar' | 'regular' | 'exceptional'>>
  includeEscapes: boolean
  setIncludeEscapes: Dispatch<SetStateAction<boolean>>
  game?: Game
  createGame: (player?: Player) => Promise<Game | undefined>
  createRematchGame: (oldGame: Game, player?: Player) => Promise<Game | undefined>
  setLoading: Dispatch<SetStateAction<boolean>>
  loadGame: (gameCode: string) => Promise<Game | undefined>
  setGame: (game?: Game) => void
  setPlayer: Dispatch<SetStateAction<Player | undefined>>
  loadPlayer: (playerToken: string) => Promise<Player | undefined>
  level: string
  setLevel: Dispatch<SetStateAction<string>>
  playLevel: import('./play-level').PlayLevel
  setPlayLevel: (playLevel: import('./play-level').PlayLevel) => void
  taxOrder?: TaxOrder
  setTaxOrder?: Dispatch<SetStateAction<TaxOrder | undefined>>
  taxFamily?: TaxFamily
  setTaxFamily?: Dispatch<SetStateAction<TaxFamily | undefined>>
  speciesGroup?: SpeciesGroup
  setSpeciesGroup?: Dispatch<SetStateAction<SpeciesGroup | undefined>>
  season: string
  setSeason: Dispatch<SetStateAction<string>>
  length: string
  setLength: Dispatch<SetStateAction<string>>
  country: Country | undefined
  setCountry: Dispatch<SetStateAction<Country>>
  language?: string
  setLanguage?: Dispatch<SetStateAction<string>>
  /** App UI language (menus/buttons). Distinct from bird-name `language`. */
  appLanguage?: string
  /** Persist app UI language to localStorage and profile.app_language (if authenticated).
   *  By default also switches bird-name language (including in-progress games). */
  setAppLanguage?: (lang: string, options?: { syncSpeciesLanguage?: boolean }) => void
  /** Switch bird-name language for this session, player, and in-progress game. */
  applySpeciesLanguage?: (lang: string) => void
  /** @deprecated Use setAppLanguage. */
  setUserPreferredLanguage?: (lang: string) => void
  visualStyle?: import('../user/visual-style').VisualStyle
  setVisualStyle?: (style: import('../user/visual-style').VisualStyle) => void
  /** Language for species names (game > profile > en). */
  speciesLanguage?: string
  multiplayer?: string
  setMultiplayer?: Dispatch<SetStateAction<string>>
  mediaType: string
  setMediaType: Dispatch<SetStateAction<string>>
  soundsScope: 'all' | 'passerines'
  setSoundsScope: Dispatch<SetStateAction<'all' | 'passerines'>>
  species?: Species[]
  speciesLoading?: boolean
  loading?: boolean
};

const AppContext = createContext<SharedState>({
  createPlayer: async () => undefined,
  createGame: async () => undefined,
  createRematchGame: async () => undefined,
  species: [],
  speciesLoading: false,
  loading: false,
  setLoading: () => false,
  loadGame: async () => undefined,
  setGame: () => {},
  setPlayer: () => {},
  loadPlayer: async () => undefined,
  includeEscapes: false,
  setIncludeEscapes: () => {},
  rarity: 'regular',
  setRarity: () => {},
  level: 'advanced',
  setLevel: () => {},
  playLevel: 'advanced',
  setPlayLevel: () => {},
  taxOrder: undefined,
  setTaxOrder: () => {},
  taxFamily: undefined,
  setTaxFamily: () => {},
  speciesGroup: undefined,
  setSpeciesGroup: () => {},
  season: '',
  setSeason: () => {},
  length: '20',
  setLength: () => {},
  country: { code: '', name: '' },
  setCountry: () => {},
  speciesLanguage: 'en',
  visualStyle: 'classic',
  setVisualStyle: () => {},
  appLanguage: 'en',
  mediaType: 'images',
  setMediaType: () => {},
  soundsScope: 'all',
  setSoundsScope: () => {},
  setAppLanguage: () => {},
  setUserPreferredLanguage: () => {}
});

export default AppContext;