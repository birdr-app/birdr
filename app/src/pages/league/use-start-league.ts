import { useCallback, useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { leagueErrorMessage, setLeaguePlayContext, startLeagueToday } from '../../api/league';
import AppContext from '../../core/app-context';
import { trackFeature } from '../../analytics/usage';

type StartOptions = {
  countryCode: string;
  countryName?: string;
  source: 'league_home' | 'home';
  resume?: boolean;
};

/** Starts (or resumes) today's league quiz and hands over to the shared solo game flow. */
export function useStartLeague() {
  const navigate = useNavigate();
  const { loadPlayer, setGame } = useContext(AppContext);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(
    async ({ countryCode, countryName, source, resume }: StartOptions) => {
      if (starting) return;
      setStarting(true);
      setError(null);
      try {
        const result = await startLeagueToday(countryCode);
        localStorage.setItem('game-token', result.game.token);
        localStorage.setItem('player-token', result.player_token);
        setLeaguePlayContext({
          countryCode,
          countryName,
          attemptId: result.attempt_id,
          gameToken: result.game.token,
        });
        await loadPlayer(result.player_token);
        setGame(result.game);
        trackFeature(
          '/league/play',
          { source, resume: !!resume, length: result.length },
          countryCode,
        );
        navigate('/game/play');
      } catch (e: unknown) {
        setError(leagueErrorMessage(e, 'Could not start today’s quiz'));
      } finally {
        setStarting(false);
      }
    },
    [starting, loadPlayer, setGame, navigate],
  );

  return { start, starting, error };
}
