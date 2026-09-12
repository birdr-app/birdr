import { playFullSrc, playPreviewSrc } from '../utils/playImageUrl';

describe('playPreviewSrc / playFullSrc', () => {
  it('upgrades http Flickr URLs so Android release can load them', () => {
    const httpFlickr = 'http://live.staticflickr.com/3715/12100643553_d86da1d356_b.jpg';
    expect(playPreviewSrc(httpFlickr)).toBe(
      'https://live.staticflickr.com/3715/12100643553_d86da1d356_z.jpg',
    );
  });
});
