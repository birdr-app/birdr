import { isUnsupportedAppLink, routeForOpenUrl } from '../lib/deepLinkRoute';

describe('routeForOpenUrl', () => {
  it('opens Survival from universal and custom scheme links', () => {
    for (const url of [
      'https://birdr.pro/open/survival/',
      'https://birdr.pro/open/survival',
      'https://birdr.pro/open/survival/?utm_source=appstore',
      'birdr://survival',
      'birdr://survival/',
    ]) {
      expect(routeForOpenUrl(url)).toEqual({ name: 'SurvivalStart' });
    }
  });

  it('opens the League, with an optional country', () => {
    expect(routeForOpenUrl('https://birdr.pro/open/league/')).toEqual({ name: 'League' });
    expect(routeForOpenUrl('birdr://league')).toEqual({ name: 'League' });
    expect(routeForOpenUrl('https://birdr.pro/open/league/nl/')).toEqual({
      name: 'League',
      params: { countryCode: 'NL' },
    });
    expect(routeForOpenUrl('birdr://league/NL')).toEqual({
      name: 'League',
      params: { countryCode: 'NL' },
    });
  });

  it('ignores other links', () => {
    for (const url of [
      'https://birdr.pro/open/app/',
      'https://birdr.pro/survival/',
      'https://birdr.pro/open/survival/extra/',
      'https://birdr.pro/open/league/nl/leaderboard/',
      'birdr://home',
      'birdr://join/abcd1234',
    ]) {
      expect(routeForOpenUrl(url)).toBeNull();
    }
  });
});

describe('isUnsupportedAppLink', () => {
  it('flags app links this version cannot route', () => {
    for (const url of [
      'https://birdr.pro/join/x/new-mode/',
      'https://birdr.pro/open/something-new/',
      'https://birdr.pro/s/abc/extra',
      'birdr://new-mode/123',
    ]) {
      expect(isUnsupportedAppLink(url)).toBe(true);
    }
  });

  it('leaves web pages, dev client and login callbacks alone', () => {
    for (const url of [
      'https://birdr.pro/flocks/results/abc/',
      'https://birdr.pro/site/how-it-works/',
      'https://birdr.pro/',
      'birdr://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081',
      'birdr://auth/google?code=x',
      'exp+birdr://expo-development-client/',
    ]) {
      expect(isUnsupportedAppLink(url)).toBe(false);
    }
  });
});
