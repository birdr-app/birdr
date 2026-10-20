import axios from './axios-config';

export type MemberCountryChallenge = {
  country_code: string;
  country_name: string;
  level_title: string;
  level_icon_url: string;
  step_label: string;
  step_number: number;
  step_total: number;
  is_champion: boolean;
  level_index: number;
};

export type MemberSurvivalRecord = {
  country_code: string;
  country_name: string;
  streak: number;
};

export type MemberLeagueRow = {
  country_code: string;
  country_name: string;
  flag: string;
  daily_wins: number;
  week_champions: number;
};

export type MemberStats = {
  member_since: string;
  games_played: number;
  correct_answers: number;
  species_identified: number;
  country_challenges: MemberCountryChallenge[];
  survival: {
    best_streak: number;
    best_country_code: string;
    best_country_name: string;
    countries_played: number;
    records: MemberSurvivalRecord[];
  };
  national_league: {
    memberships: number;
    daily_wins: number;
    week_champions: number;
    quizzes_played: number;
    leagues: MemberLeagueRow[];
  };
  flocks_joined: number;
  best_score: {
    score: number;
    country_code: string;
    country_name: string;
    level: string;
    length: number;
  } | null;
};

export async function fetchMemberStats(): Promise<MemberStats> {
  const { data } = await axios.get<MemberStats>('/api/member-stats/');
  return data;
}
