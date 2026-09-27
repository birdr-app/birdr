import {
  filterPickerCountries,
  groupCountriesForPicker,
  isStatePickerRegion,
  regionsForParent,
  statePickerParentCode,
  statesForParent,
} from '../data/country-groups';
import { isPersistableCountryCode } from '../user/country-preference';

describe('country picker grouping', () => {
  const countries = [
    { code: 'US', name: 'United States', kind: 'country' },
    { code: 'US-MA', name: 'Massachusetts', parent: 'US', kind: 'subnational' },
    { code: 'US-AK', name: 'Alaska', parent: 'US', kind: 'subnational' },
    { code: 'US-EAST', name: 'United States – Eastern', parent: 'US', kind: 'aggregate' },
    { code: 'CN', name: 'China', kind: 'country' },
    { code: 'CN-SOUTH', name: 'China – South & Southwest', parent: 'CN', kind: 'aggregate' },
    { code: 'NL', name: 'Netherlands', kind: 'country' },
    { code: 'NL-NH', name: 'Texel Bird Week', parent: 'NL', kind: 'specialty' },
  ];

  test('hides specialty regions', () => {
    const filtered = filterPickerCountries(countries, true);
    expect(filtered.map((c) => c.code)).not.toContain('NL-NH');
  });

  test('country list is only countries and world', () => {
    const filtered = filterPickerCountries(
      [...countries, { code: 'world', name: 'World', kind: 'country' }],
      true
    );
    const { groups, standalone } = groupCountriesForPicker(filtered);
    expect(groups).toEqual([]);
    expect(standalone.map((c) => c.code).sort()).toEqual(['CN', 'NL', 'US', 'world']);
  });

  test('identifies the All / state picker parent', () => {
    expect(statePickerParentCode(countries.find((c) => c.code === 'US'))).toBe('US');
    expect(statePickerParentCode(countries.find((c) => c.code === 'US-MA'))).toBe('US');
    expect(statePickerParentCode(countries.find((c) => c.code === 'US-AK'))).toBe('US');
    expect(statePickerParentCode(countries.find((c) => c.code === 'US-EAST'))).toBe('US');
    expect(statePickerParentCode(countries.find((c) => c.code === 'CN-SOUTH'))).toBe('CN');
    expect(isStatePickerRegion(countries.find((c) => c.code === 'US-MA')!)).toBe(true);
    expect(isStatePickerRegion(countries.find((c) => c.code === 'US-AK')!)).toBe(true);
    expect(statesForParent(countries, 'US').map((c) => c.code).sort()).toEqual(['US-AK', 'US-MA']);
    const usRegions = regionsForParent(countries, 'US');
    expect(usRegions.aggregates.map((c) => c.code)).toEqual(['US-EAST']);
    expect(usRegions.subnationals.map((c) => c.code).sort()).toEqual(['US-AK', 'US-MA']);
  });

  test('persists hyphenated region codes', () => {
    expect(isPersistableCountryCode('US-MA')).toBe(true);
    expect(isPersistableCountryCode('')).toBe(false);
  });
});
