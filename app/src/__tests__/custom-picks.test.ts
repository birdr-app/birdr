import {
  addCustomPick,
  customPickKey,
  CUSTOM_PICKS_STORAGE_KEY,
  readCustomPicks,
  removeCustomPick,
} from '../user/custom-picks'

const robin = { id: 1, name: 'Robin' }
const wren = { id: 2, name: 'Wren' }
const finch = { id: 3, name: 'Finch' }

describe('custom picks', () => {
  beforeEach(() => localStorage.clear())

  test('keys ignore the order of the birds', () => {
    expect(customPickKey([3, 1, 2])).toBe('1-2-3')
  })

  test('adds new picks on top and replaces a duplicate selection', () => {
    addCustomPick([robin, wren])
    addCustomPick([robin, wren, finch])
    const picks = addCustomPick([wren, robin])
    expect(picks.map((p) => p.key)).toEqual(['1-2', '1-2-3'])
    expect(readCustomPicks()).toEqual(picks)
  })

  test('removes a pick by key', () => {
    addCustomPick([robin, wren])
    addCustomPick([robin, finch])
    expect(removeCustomPick('1-2').map((p) => p.key)).toEqual(['1-3'])
    expect(readCustomPicks().map((p) => p.key)).toEqual(['1-3'])
  })

  test('ignores corrupt storage', () => {
    localStorage.setItem(CUSTOM_PICKS_STORAGE_KEY, 'nope')
    expect(readCustomPicks()).toEqual([])
    localStorage.setItem(CUSTOM_PICKS_STORAGE_KEY, JSON.stringify([{ species: [robin] }]))
    expect(readCustomPicks()).toEqual([])
  })
})
