import * as React from "react"
import {useEffect} from "react"
import {AppContextProvider} from "./core/app-context-provider";
import {AuthProfileProvider} from "./core/auth-profile-context";
import {WebsocketContextProvider} from "./core/websocket-context-provider"
import {MainContent} from "./main-content"
import {registerServiceWorker} from "./core/register-service-worker"
import { ChakraProvider } from '@chakra-ui/react'
import { system } from './theme'
import { Toaster } from "@/components/ui/toaster";
import { ApiAvailabilityGate } from "./components/api-availability-gate";

registerServiceWorker()

export const App = () => {
  useEffect(() => {
    document.title = "Birdr"
  }, [])

  return (
    <ChakraProvider value={system}>
      <Toaster />
      <ApiAvailabilityGate>
        <AuthProfileProvider>
          <AppContextProvider>
            <WebsocketContextProvider>
              <MainContent/>
            </WebsocketContextProvider>
          </AppContextProvider>
        </AuthProfileProvider>
      </ApiAvailabilityGate>
    </ChakraProvider>
  )
}

export default App

