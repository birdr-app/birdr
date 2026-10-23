import { Badge } from "@chakra-ui/react";
import { FormattedMessage } from "react-intl";
import { Link as RouterLink } from "react-router-dom";
import { FaTrophy } from "react-icons/fa";
import { buildHiscoresPath, GameHiscoresFilter } from "../core/hiscores-link";

/** Player's position in the hiscores for this game's options; hidden when the game has no rank. */
export const HiscoreRank = ({
  game,
  rank,
}: {
  game: GameHiscoresFilter;
  rank?: number | null;
}) => {
  if (!rank) return null;
  return (
    <Badge asChild colorPalette={rank === 1 ? 'yellow' : 'primary'} cursor="pointer" data-testid="game-detail-hiscore-rank">
      <RouterLink to={buildHiscoresPath(game)}>
        <FaTrophy />
        <FormattedMessage
          id="hiscore_rank"
          defaultMessage="#{rank} in the high scores"
          values={{ rank }}
        />
      </RouterLink>
    </Badge>
  );
};
