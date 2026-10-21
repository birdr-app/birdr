import { routeForOpenUrl } from '../lib/deepLinkRoute';

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
