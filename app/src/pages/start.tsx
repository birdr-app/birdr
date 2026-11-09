import {Heading} from "@chakra-ui/react";
import { Page } from "../shared/components/layout";
import {FormattedMessage} from "react-intl";
import {CreateGame} from "../components/create-game"
import {useContext} from "react"
import AppContext from "../core/app-context"
import {Loading} from "../components/loading"
import {useSearchParams} from "react-router-dom"
import type {PlayLevel} from "../core/play-level"

const StartPage = () => {
  const {player, loading} = useContext(AppContext);
  // /start?country=CR&level=advanced: a link can preset the country and level (e.g. after Trip prep).
  const [params] = useSearchParams();
  const country = params.get('country')?.toUpperCase() || undefined;
  const level = params.get('level') as PlayLevel | null;

  return (
    <Page>
      <Page.Header>
        <Heading color={'gray.800'} size={'lg'} m={0}>
          {player ? player.name : <FormattedMessage id='welcome' defaultMessage={'Welcome'}/>}
        </Heading>
      </Page.Header>
      <Page.Body>
        {loading ? (
          <Loading/>
        ) : (
          <CreateGame country={country} playLevel={level ?? undefined}/>
        )}
      </Page.Body>
    </Page>

  )
};

export default StartPage;