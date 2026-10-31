import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import {
  OPEN_IN_APP_SESSION_KEY,
  shouldTryOpenInApp,
  tryOpenInApp,
} from '../utils/openInApp';

/**
 * On mobile browsers, try opening the native Motmot app once per session.
 * If the app is not installed, the user stays on the website.
 */
export function OpenInAppOnLoad() {
  const { pathname } = useLocation();

  useEffect(() => {
    if (!shouldTryOpenInApp(pathname)) return;
    if (sessionStorage.getItem(OPEN_IN_APP_SESSION_KEY)) return;

    sessionStorage.setItem(OPEN_IN_APP_SESSION_KEY, '1');
    const timer = window.setTimeout(() => {
      tryOpenInApp(pathname);
    }, 600);

    return () => window.clearTimeout(timer);
  }, [pathname]);

  return null;
}
