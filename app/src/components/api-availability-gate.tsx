import { Flex, Spinner } from '@chakra-ui/react';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { IntlProvider } from 'react-intl';
import { probeApiAvailability } from '../api/apiAvailability';
import {
  APP_LOCALE_STORAGE_KEY,
  resolveAppLocale,
} from '../i18n/app-locales';
import enMessages from '../locales/en.json';
import { ApiUnavailableScreen } from './api-unavailable-screen';

type Catalog = Record<string, string>;

const catalogLoaders: Record<string, () => Promise<{ default: Catalog }>> = {
  nl: () => import('../locales/nl.json'),
  es: () => import('../locales/es.json'),
  fr: () => import('../locales/fr.json'),
  de: () => import('../locales/de.json'),
  it: () => import('../locales/it.json'),
  'pt-BR': () => import('../locales/pt-BR.json'),
  ja: () => import('../locales/ja.json'),
};

const RETRY_INTERVAL_MS = 15000;

type Props = {
  children: ReactNode;
};

type Status = 'checking' | 'reachable' | 'unreachable';

function storedLocale() {
  try {
    return resolveAppLocale({ stored: localStorage.getItem(APP_LOCALE_STORAGE_KEY) });
  } catch {
    return resolveAppLocale({});
  }
}

export function ApiAvailabilityGate({ children }: Props) {
  const [status, setStatus] = useState<Status>('checking');
  const [retrying, setRetrying] = useState(false);
  const [locale] = useState(storedLocale);
  const [messages, setMessages] = useState<Catalog>(enMessages);
  const [activeLocale, setActiveLocale] = useState(locale === 'en' ? 'en' : locale);

  const check = useCallback(async (showRetrying: boolean) => {
    if (showRetrying) setRetrying(true);
    const result = await probeApiAvailability();
    setStatus(result);
    if (showRetrying) setRetrying(false);
  }, []);

  useEffect(() => {
    void check(false);
  }, [check]);

  useEffect(() => {
    if (status !== 'unreachable') return undefined;
    const id = window.setInterval(() => {
      void check(true);
    }, RETRY_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [status, check]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        void check(status === 'unreachable');
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [check, status]);

  useEffect(() => {
    if (locale === 'en') {
      setMessages(enMessages);
      setActiveLocale('en');
      return;
    }
    const loader = catalogLoaders[locale];
    if (!loader) return;
    let cancelled = false;
    loader()
      .then((m) => {
        if (!cancelled) {
          setMessages({ ...enMessages, ...m.default });
          setActiveLocale(locale);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMessages(enMessages);
          setActiveLocale('en');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  if (status === 'checking') {
    return (
      <Flex minH="100vh" align="center" justify="center" bg="primary.50">
        <Spinner size="xl" color="primary.400" />
      </Flex>
    );
  }

  if (status === 'unreachable') {
    return (
      <IntlProvider locale={activeLocale} defaultLocale="en" messages={messages}>
        <ApiUnavailableScreen onRetry={() => void check(true)} retrying={retrying} />
      </IntlProvider>
    );
  }

  return <>{children}</>;
}
