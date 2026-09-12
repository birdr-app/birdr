import * as React from "react"
import {useContext, useEffect} from "react"
import {BrowserRouter, Route, Routes} from "react-router-dom";
import { Layout } from "./shared/components/layout";
import HomePage from "./pages/home";
import { MarketingHomePage } from "./pages/marketing-home";
import Lobby from "./pages/mpg/lobby"
import {AboutPage} from "./pages/about";
import {IntlProvider} from "react-intl";

import enMessages from './locales/en.json';
import nlMessages from './locales/nl.json';
import esMessages from './locales/es.json';
import frMessages from './locales/fr.json';
import deMessages from './locales/de.json';
import itMessages from './locales/it.json';
import ptBRMessages from './locales/pt-BR.json';
import jaMessages from './locales/ja.json';
import MultiPlayerGame from "./pages/mpg/multi-player-game"
import AppContext from "./core/app-context"
import StartPage from "./pages/start"
import JoinPage from "./pages/join"
import GameEnded from "./pages/mpg/results"
import Hiscores from "./pages/hiscores"
import Updates from "./pages/updates"
import {Login} from "./components/auth/login"
import {AuthCallback} from "./components/auth/auth-callback"
import {AuthLoginRedirect} from "./components/auth/auth-login-redirect"
import {PrivacyPage} from "./pages/privacy"
import {ProfilePage} from "./pages/profile"
import { ForgotPasswordPage } from "./pages/forgot-password";
import { ResetPasswordPage } from "./pages/reset-password";
import TexelStartPage from "./pages/texel/start"
import TexelHiscorePage from "./pages/texel/hiscores"
import { MyGamesPage } from "./pages/my-games"
import ChecklistPage from "./pages/checklist"
import TroubleSpotsPage from "./pages/trouble-spots"
import TroubleSpotPairPage from "./pages/trouble-spot-pair"
import TroubleSpotSpeciesPage from "./pages/trouble-spot-species"
import SpeciesPracticePage from "./pages/practice-species"
import PairPracticePage from "./pages/practice-pair"
import { BirdrJourneyListPage } from "./pages/birdr-journey/list"
import { CountryChallengeLeaderboardPage } from "./pages/birdr-journey/leaderboard"
import { BirdrJourneyIntroPage } from "./pages/birdr-journey/intro"
import { BirdrJourneyCountryPage } from "./pages/birdr-journey/country"
import { BirdrJourneyProgressPage } from "./pages/birdr-journey/progress"
import { BirdrJourneyStepIntroPage } from "./pages/birdr-journey/step-intro"
import { BirdrJourneyStepResultsPage } from "./pages/birdr-journey/step-results"
import { BirdrJourneyLevelCelebrationPage } from "./pages/birdr-journey/level-celebration"
import { BirdrJourneyPlayPage } from "./pages/birdr-journey/play"
import { GameDetailPage } from "./pages/game-detail"
import { MediaReviewPage } from "./pages/media-review"
import { HelpOverviewPage, HelpPageDetail } from "./pages/help"
import UpdateDetailPage from "./pages/update-detail"
import { AnalyticsTracker } from "./components/analytics-tracker"
import { FlocksListPage } from "./pages/flocks/list"
import { FlocksIntroPage } from "./pages/flocks/intro"
import { FlocksCreatePage } from "./pages/flocks/create"
import { FlocksJoinPage } from "./pages/flocks/join"
import { FlockDetailPage } from "./pages/flocks/detail"
import { FlockMembersPage } from "./pages/flocks/members"
import { FlockInvitePage } from "./pages/flocks/invite"
import { FlockLeaderboardPage } from "./pages/flocks/leaderboard"
import { FlockInviteLandingPage } from "./pages/flocks/invite-landing"
import { FlockResultPage } from "./pages/flocks/result"
import { GameShareResultPage } from "./pages/game-share-result"
export const MainContent = () => {
  useEffect(() => {
    document.title = "Birdr"

  }, []);
  const {appLanguage} = useContext(AppContext)

  const catalogs: Record<string, Record<string, string>> = {
    en: enMessages,
    nl: nlMessages,
    es: esMessages,
    fr: frMessages,
    de: deMessages,
    it: itMessages,
    'pt-BR': ptBRMessages,
    ja: jaMessages,
  }
  const locale = appLanguage && catalogs[appLanguage] ? appLanguage : 'en';
  const messages = { ...enMessages, ...(catalogs[locale] || {}) };

  return (
    <IntlProvider locale={locale} defaultLocale="en" messages={messages}>
      <BrowserRouter>
        <AnalyticsTracker />
        <Routes>
          <Route path="/" element={<MarketingHomePage />} />
          <Route element={<Layout/>}>
            <Route path="/play" element={<HomePage/>}/>
            <Route path="/login" element={<Login />} />
            <Route path="/login/:provider" element={<AuthCallback />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password/:uid/:token" element={<ResetPasswordPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/settings" element={<ProfilePage />} />
            <Route path="/my-games" element={<MyGamesPage />} />
            <Route path="/checklist" element={<ChecklistPage />} />
            <Route path="/trouble-spots" element={<TroubleSpotsPage />} />
            <Route path="/trouble-spots/species/:speciesId" element={<TroubleSpotSpeciesPage />} />
            <Route path="/trouble-spots/pair/:lowId/:highId" element={<TroubleSpotPairPage />} />
            <Route path="/practice/species/:slug" element={<SpeciesPracticePage />} />
            <Route path="/practice/pair/:pair" element={<PairPracticePage />} />
            <Route path="/flocks/intro" element={<FlocksIntroPage />} />
            <Route path="/flocks/create" element={<FlocksCreatePage />} />
            <Route path="/flocks/join" element={<FlocksJoinPage />} />
            <Route path="/flocks/list" element={<FlocksListPage />} />
            <Route path="/flocks/results/:token" element={<FlockResultPage />} />
            <Route path="/g/:token" element={<GameShareResultPage />} />
            <Route path="/flocks/:slug/members" element={<FlockMembersPage />} />
            <Route path="/flocks/:slug/invite" element={<FlockInvitePage />} />
            <Route
              path="/flocks/:slug/challenges/:challengeId/leaderboard"
              element={<FlockLeaderboardPage />}
            />
            <Route path="/flocks/:slug" element={<FlockDetailPage />} />
            <Route path="/join/flock/:token/web" element={<FlockInviteLandingPage />} />
            <Route path="/join/flock/:token" element={<FlockInviteLandingPage />} />
            <Route path="/journey" element={<BirdrJourneyListPage />} />
            <Route path="/journey/leaderboard" element={<CountryChallengeLeaderboardPage />} />
            <Route path="/journey/intro" element={<BirdrJourneyIntroPage />} />
            <Route path="/journey/country" element={<BirdrJourneyCountryPage />} />
            <Route path="/journey/play" element={<BirdrJourneyPlayPage />} />
            <Route path="/journey/:countryCode/celebration" element={<BirdrJourneyLevelCelebrationPage />} />
            <Route path="/journey/:countryCode/step" element={<BirdrJourneyStepIntroPage />} />
            <Route path="/journey/:countryCode/results" element={<BirdrJourneyStepResultsPage />} />
            <Route path="/journey/:countryCode" element={<BirdrJourneyProgressPage />} />
            <Route path="/my-games/:token" element={<GameDetailPage />} />
            <Route path='/start/' element={<StartPage />}/>
            <Route path='/join/' element={<JoinPage />}/>
            <Route path="/join/:gameCode" element={<JoinPage/>}/>
            <Route path='/join/:gameCode/web' element={<JoinPage/>}/>
            <Route path='/about/' element={<AboutPage/>}/>
            <Route path='/privacy/' element={<PrivacyPage/>}/>
            <Route path='/texel/start/' element={<TexelStartPage />}/>
            <Route path='/texel/scores/' element={<TexelHiscorePage />}/>

            <Route path="/game/lobby" element={<Lobby/>}/>
            <Route path="/game/play" element={<MultiPlayerGame/>}/>
            <Route path="/game/ended" element={<GameEnded/>}/>

            <Route path='/scores/' element={<Hiscores />}/>
            <Route path='/updates/' element={<Updates />}/>
            <Route path='/updates/:id' element={<UpdateDetailPage />}/>
            <Route path='/help' element={<HelpOverviewPage />}/>
            <Route path='/help/:slug' element={<HelpPageDetail />}/>
            <Route path='/media-review/' element={<MediaReviewPage />}/>
            <Route path='/media-review/:countryCode' element={<MediaReviewPage />}/>

          </Route>
        </Routes>
      </BrowserRouter>
    </IntlProvider>
  )
}

