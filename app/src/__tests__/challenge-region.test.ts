import { countryCodeToFlag } from '../api/birdrJourney';
import { getChallengeCountryName } from '../data/country-names-nl';

describe('Country Challenge region labels', () => {
  const canada = { code: 'CA', name: 'Canada' };
  const ontario = { code: 'CA-ON', name: 'Ontario', parent: 'CA', parent_name: 'Canada', kind: 'subnational' };
  const usEast = {
    code: 'US-EAST',
    name: 'United States – Eastern',
    parent: 'US',
    parent_name: 'United States',
    kind: 'aggregate',
  };

  test('a whole country keeps its plain name', () => {
    expect(getChallengeCountryName(canada, 'en')).toBe('Canada');
  });

  test('a region carries its country', () => {
    expect(getChallengeCountryName(ontario, 'en')).toBe('Ontario, Canada');
    expect(getChallengeCountryName(ontario, 'nl')).toBe('Ontario, Canada');
    expect(getChallengeCountryName({ ...ontario, parent: 'NL', parent_name: 'Netherlands' }, 'nl')).toBe(
      'Ontario, Nederland'
    );
  });

  test('an aggregate already names its country', () => {
    expect(getChallengeCountryName(usEast, 'en')).toBe('United States – Eastern');
  });

  test('a region shows its country flag', () => {
    expect(countryCodeToFlag('CA')).toBe('🇨🇦');
    expect(countryCodeToFlag('CA-ON')).toBe('🇨🇦');
    expect(countryCodeToFlag('US-EAST')).toBe('🇺🇸');
    expect(countryCodeToFlag('IBERIA')).toBe('🇪🇸🇵🇹');
  });
});
