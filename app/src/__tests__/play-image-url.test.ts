import { playFullSrc, playPreviewSrc } from '../utils/play-image-url';

describe('playPreviewSrc / playFullSrc', () => {
  const wiki960 =
    'https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Bar-tailed_Godwit.jpg/960px-Bar-tailed_Godwit.jpg';
  const inatOriginal =
    'https://inaturalist-open-data.s3.amazonaws.com/photos/604502879/original.jpg';
  const cornell =
    'https://cdn.download.ams.birds.cornell.edu/api/v1/asset/12345/1800';

  it('uses 500px Wikimedia thumbs in gameplay and 960px when zooming', () => {
    expect(playPreviewSrc(wiki960)).toContain('/500px-Bar-tailed_Godwit.jpg');
    expect(playFullSrc(wiki960)).toContain('/960px-Bar-tailed_Godwit.jpg');
    expect(playFullSrc(playPreviewSrc(wiki960))).toContain('/960px-');
  });

  it('uses iNaturalist medium in gameplay and large when zooming', () => {
    expect(playPreviewSrc(inatOriginal)).toMatch(/\/medium\.jpg$/);
    expect(playFullSrc(inatOriginal)).toMatch(/\/large\.jpg$/);
    expect(playFullSrc(playPreviewSrc(inatOriginal))).toMatch(/\/large\.jpg$/);
  });

  it('uses Cornell 640 in gameplay (no 500 step) and 1800 when zooming', () => {
    expect(playPreviewSrc(cornell)).toMatch(/\/640$/);
    expect(playFullSrc(cornell)).toMatch(/\/1800$/);
    expect(playFullSrc(playPreviewSrc(cornell))).toMatch(/\/1800$/);
  });

  it('leaves unrelated URLs unchanged', () => {
    const other = 'https://cdn.example.com/birds/photo.jpg';
    expect(playPreviewSrc(other)).toBe(other);
    expect(playFullSrc(other)).toBe(other);
  });

  it('upgrades http Flickr URLs so Android release can load them', () => {
    const httpFlickr = 'http://live.staticflickr.com/3715/12100643553_d86da1d356_b.jpg';
    expect(playPreviewSrc(httpFlickr)).toBe(
      'https://live.staticflickr.com/3715/12100643553_d86da1d356_z.jpg',
    );
  });
});
