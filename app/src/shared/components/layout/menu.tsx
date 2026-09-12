import {Flex, Link} from "@chakra-ui/react";
import {FormattedMessage} from "react-intl"
import {Link as RouterLink} from "react-router-dom";
import { getCountryChallengeLeaderboardPath } from "../../../api/birdrJourney";

export const BirdrMenu = () => {
    return (
        <Flex direction={'column'} gap={4} fontSize={'xl'}>
            <Link href={'/play'} textDecoration="none">
              <FormattedMessage id={'home'} defaultMessage={'Home'}/>
            </Link>
            <Link href={'/start'} textDecoration="none">
              <FormattedMessage id={'new game'} defaultMessage={'New game'} />
            </Link>
            <Link href={'/scores'} textDecoration="none">
              <FormattedMessage id={'High scores'} defaultMessage={'High scores'} />
            </Link>
            <Link asChild textDecoration="none">
              <RouterLink to={getCountryChallengeLeaderboardPath()}>
                <FormattedMessage
                  id="country_leaderboard"
                  defaultMessage="Country leaderboard"
                />
              </RouterLink>
            </Link>
            <Link href={'/checklist'} textDecoration="none">
              <FormattedMessage id="checklist_title" defaultMessage="My Checklist" />
            </Link>
            <Link href={'/updates'} textDecoration="none">
              <FormattedMessage id={'Updates'} defaultMessage={'Updates'} />
            </Link>
            <Link href={'/help'} textDecoration="none">
              <FormattedMessage id={'help'} defaultMessage={'Help'} />
            </Link>
            <Link href={'/privacy'} textDecoration="none">
              <FormattedMessage id={'privacy'} defaultMessage={'Privacy'} />
            </Link>
            <Link href={'/about'} textDecoration="none">
              <FormattedMessage id={'about birdr'} defaultMessage={'About Birdr'} />
            </Link>
        </Flex>
    );
}

export default BirdrMenu;
