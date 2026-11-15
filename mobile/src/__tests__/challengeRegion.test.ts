import { getChallengeCountryName } from '../i18n/countryNames';

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

  it('keeps a whole country plain', () => {
    expect(getChallengeCountryName(canada, 'en')).toBe('Canada');
  });

  it('names the country of a region', () => {
    expect(getChallengeCountryName(ontario, 'en')).toBe('Ontario, Canada');
    expect(getChallengeCountryName({ ...ontario, parent: 'NL', parent_name: 'Netherlands' }, 'nl')).toBe(
      'Ontario, Nederland',
    );
  });

  it('leaves an aggregate alone', () => {
    expect(getChallengeCountryName(usEast, 'en')).toBe('United States – Eastern');
  });
});
