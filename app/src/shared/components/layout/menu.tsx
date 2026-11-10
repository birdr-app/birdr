import {Box, Flex, Link} from "@chakra-ui/react";
import { useContext } from "react";
import {FormattedMessage} from "react-intl"
import {Link as RouterLink} from "react-router-dom";
import { getCountryChallengeLeaderboardPath } from "../../../api/birdrJourney";
import { COURSE_LOCALES } from "../../../api/course";
import AppContext from "../../../core/app-context";
import { useGameModes } from "../../../core/use-game-modes";

export const BirdrMenu = () => {
    // Beginners get a short menu; leagues and leaderboards appear after a few games.
    const { showMenuExtras } = useGameModes();
    const { appLanguage } = useContext(AppContext);
    // The beginners course is written in Dutch, so only the Dutch app offers it.
    const showCourse = COURSE_LOCALES.includes(appLanguage || 'en');
    return (
        <Flex direction={'column'} gap={4} fontSize={'xl'}>
            <Link href={'/play'} textDecoration="none">
              <FormattedMessage id={'home'} defaultMessage={'Home'}/>
            </Link>
            <Link asChild textDecoration="none">
              <RouterLink to={'/scores'}>
                <FormattedMessage id="game_hiscores" defaultMessage="Game high scores" />
              </RouterLink>
            </Link>
            {showMenuExtras && (
              <Link asChild textDecoration="none">
                <RouterLink to={'/league'}>
                  <FormattedMessage id="league_national" defaultMessage="National leagues" />
                </RouterLink>
              </Link>
            )}
            {showMenuExtras && (
              <Link asChild textDecoration="none">
                <RouterLink to={getCountryChallengeLeaderboardPath()}>
                  <FormattedMessage
                    id="country_leaderboard"
                    defaultMessage="Country leaderboard"
                  />
                </RouterLink>
              </Link>
            )}
            <Link asChild textDecoration="none">
              <RouterLink to={'/tricky-birds'}>
                <FormattedMessage id="trouble_spots_everyone" defaultMessage="Everyone's tricky birds" />
              </RouterLink>
            </Link>
            {showCourse && (
              <Link asChild textDecoration="none">
                <RouterLink to={'/course'}>
                  <FormattedMessage id="course_title" defaultMessage="Beginners course" />
                  <Box
                    as="span"
                    ml={2}
                    fontSize="2xs"
                    fontWeight="800"
                    letterSpacing="wider"
                    textTransform="uppercase"
                    px="1.5"
                    py="0.5"
                    borderRadius="sm"
                    bg="primary.100"
                    color="primary.700"
                    verticalAlign="middle"
                  >
                    <FormattedMessage id="beta" defaultMessage="Beta" />
                  </Box>
                </RouterLink>
              </Link>
            )}
            <Link asChild textDecoration="none">
              <RouterLink to={'/trips'}>
                <FormattedMessage id="trip_title" defaultMessage="Trip prep" />
                <Box
                    as="span"
                    ml={2}
                    fontSize="2xs"
                    fontWeight="800"
                    letterSpacing="wider"
                    textTransform="uppercase"
                    px="1.5"
                    py="0.5"
                    borderRadius="sm"
                    bg="primary.100"
                    color="primary.700"
                    verticalAlign="middle"
                  >
                    <FormattedMessage id="beta" defaultMessage="Beta" />
                  </Box>
              </RouterLink>
            </Link>
            <Link href={'/checklist'} textDecoration="none">
              <FormattedMessage id="checklist_title" defaultMessage="My checklist" />
            </Link>
            <Box borderTopWidth="1px" borderColor="gray.200" />
            <Link href={'/updates'} textDecoration="none" fontSize="md" color="gray.600">
              <FormattedMessage id={'Updates'} defaultMessage={'Updates'} />
            </Link>
            <Link href={'/help'} textDecoration="none" fontSize="md" color="gray.600">
              <FormattedMessage id={'help'} defaultMessage={'Help'} />
            </Link>
            <Link href={'/privacy'} textDecoration="none" fontSize="md" color="gray.600">
              <FormattedMessage id={'privacy'} defaultMessage={'Privacy'} />
            </Link>
            <Link href={'/about'} textDecoration="none" fontSize="md" color="gray.600">
              <FormattedMessage id={'about birdr'} defaultMessage={'About Motmot'} />
            </Link>
        </Flex>
    );
}

export default BirdrMenu;
