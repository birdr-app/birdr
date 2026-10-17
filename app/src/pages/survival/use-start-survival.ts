import { useCallback, useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { startSurvival, storeSurvivalSession } from '../../api/survival';
import AppContext, { Player } from '../../core/app-context';
import { trackFeature } from '../../analytics/usage';

export function survivalErrorMessage(error: unknown, fallback = 'Could not start Survival'): string {
  const data = (error as { response?: { data?: { error?: string | string[]; detail?: string } } })
    ?.response?.data;
  const apiError = data?.error ?? data?.detail;
  if (Array.isArray(apiError) && apiError[0]) return String(apiError[0]);
  if (typeof apiError === 'string' && apiError.trim()) return apiError;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

type StartOptions = {
  country: string;
  countryName?: string;
  language: string;
  source: 'start' | 'try_again';
};

/** Ensures a player, starts a survival run and opens the play page. */
export function useStartSurvival() {
  const navigate = useNavigate();
  const { player, createPlayer, setGame } = useContext(AppContext);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(
    async ({ country, countryName, language, source }: StartOptions) => {
      if (starting) return;
      setStarting(true);
      setError(null);
      try {
        // Reuse the stored guest token so personal bests stick to the same player.
        let token = player?.token || localStorage.getItem('player-token') || undefined;
        if (!token) {
          const created: Player | undefined = await createPlayer();
          token = created?.token;
        }
        const result = await startSurvival(country, language, token);
        localStorage.setItem('player-token', result.player_token);
        localStorage.setItem('game-token', result.game.token);
        setGame(result.game);
        storeSurvivalSession({
          gameToken: result.game.token,
          playerToken: result.player_token,
          country,
          countryName,
          language,
          countryRecord: result.country_record,
          personalBest: result.personal_best ?? 0,
        });
        trackFeature(
          source === 'try_again' ? '/survival/try-again' : '/survival/start',
          { language, personal_best: result.personal_best ?? 0 },
          country,
        );
        navigate('/survival/play');
      } catch (e: unknown) {
        setError(survivalErrorMessage(e));
      } finally {
        setStarting(false);
      }
    },
    [starting, player, createPlayer, setGame, navigate],
  );

  return { start, starting, error };
}
