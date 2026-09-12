import { playVideoFallbackUrl, playVideoStillUrl, playVideoUrl, wikimediaVideoVariants } from '../utils/playVideoUrl';

describe('playVideoUrl', () => {
  const original =
    'https://upload.wikimedia.org/wikipedia/commons/e/e6/Huiszwaluw_zittend_op_schapenhek-4961660.webm';
  const shoveler =
    'https://upload.wikimedia.org/wikipedia/commons/2/2c/Northern_shoveler_vortex_%2883216%29.webm';

  it('uses 144p MJPEG on iOS and 480p webm on Android', () => {
    expect(playVideoUrl(original, 'ios')).toContain('.144p.mjpeg.mov');
    expect(playVideoUrl(original, 'android')).toContain('.480p.vp9.webm');
  });

  it('falls back from 144p MJPEG to 360p MPEG-4 on iOS, not WebM', () => {
    const mjpeg = playVideoUrl(original, 'ios');
    const next = playVideoFallbackUrl(original, mjpeg, 'ios');
    expect(next).toContain('.360p.mpeg4.mov');
    expect(playVideoFallbackUrl(original, next!, 'ios')).toBeNull();
  });

  it('builds a Commons JPEG still', () => {
    expect(playVideoStillUrl(shoveler)).toBe(
      'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/' +
        'Northern_shoveler_vortex_%2883216%29.webm/' +
        '960px--Northern_shoveler_vortex_%2883216%29.webm.jpg',
    );
  });

  it('parses 480p API URLs back to the same iOS sources', () => {
    const webm = wikimediaVideoVariants(original)!.webm480;
    expect(playVideoUrl(webm, 'ios')).toBe(playVideoUrl(original, 'ios'));
    expect(wikimediaVideoVariants(shoveler)?.mov144).toContain('.144p.mjpeg.mov');
  });
});
