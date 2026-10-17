import { useCallback } from 'react';
import { useGame } from '../context/GameContext';
import { startSurvival } from '../api/survival';
import * as playerApi from '../api/player';

export type SurvivalPlayParams = {
  gameToken: string;
  playerToken: string;
  countryCode: string;
  language: string;
  /** Country record streak before this run; null when nobody has played this country yet. */
  countryRecord: number | null;
  personalBest: number;
};

/** Starts a survival run on the server and loads it into GameContext; returns the SurvivalPlay params. */
export function useStartSurvival() {
  const { loadGame, setPlayer } = useGame();

  return useCallback(
    async (countryCode: string, language: string, playerToken?: string | null): Promise<SurvivalPlayParams> => {
      const result = await startSurvival(countryCode, language, playerToken);
      const player = await playerApi.getPlayer(result.player_token).catch(() => null);
      if (player) setPlayer(player);
      await loadGame(result.game.token);
      return {
        gameToken: result.game.token,
        playerToken: result.player_token,
        countryCode,
        language,
        countryRecord: result.country_record?.streak ?? null,
        personalBest: result.personal_best ?? 0,
      };
    },
    [loadGame, setPlayer],
  );
}
