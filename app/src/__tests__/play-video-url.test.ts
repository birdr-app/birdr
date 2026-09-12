import { playVideoSources, wikimediaVideoVariants } from '../utils/play-video-url';

describe('wikimedia video playback URLs', () => {
  const original =
    'https://upload.wikimedia.org/wikipedia/commons/e/e6/Huiszwaluw_zittend_op_schapenhek-4961660.webm';
  const ogv = 'https://upload.wikimedia.org/wikipedia/commons/e/e0/Pinicola_enucleator_CT2.ogv';

  it('builds 480p webm and 360p mov from the original path', () => {
    const v = wikimediaVideoVariants(original);
    expect(v?.webm480).toContain('.480p.vp9.webm');
    expect(v?.mov360).toContain('.360p.mpeg4.mov');
    expect(v?.mov144).toContain('.144p.mjpeg.mov');
    expect(v?.original).toBe(original);
  });

  it('still finds mov when the API already returned 480p webm', () => {
    const transcoded = wikimediaVideoVariants(original)!.webm480;
    expect(wikimediaVideoVariants(transcoded)?.mov360).toBe(
      wikimediaVideoVariants(original)!.mov360,
    );
    expect(wikimediaVideoVariants(transcoded)?.original).toBe(original);
  });

  it('puts mov first when preferMov, webm first otherwise', () => {
    const safari = playVideoSources(ogv, true, false);
    const chrome = playVideoSources(ogv, false, false);
    expect(safari[0].src).toContain('.144p.mjpeg.mov');
    expect(safari[0].type).toBe('video/quicktime');
    expect(safari.map((s) => s.src).some((src) => src.includes('.360p.mpeg4.mov'))).toBe(true);
    expect(safari.map((s) => s.src).some((src) => src.includes('.webm'))).toBe(true);
    expect(chrome[0].src).toContain('.480p.vp9.webm');
    expect(chrome[0].type).toBe('video/webm');
  });

  it('omits WebM on Apple touch devices and exposes a still', () => {
    const ios = playVideoSources(ogv, true, true);
    expect(ios).toHaveLength(2);
    expect(ios[0].src).toContain('.144p.mjpeg.mov');
    expect(ios[1].src).toContain('.360p.mpeg4.mov');
    expect(wikimediaVideoVariants(original)?.still).toContain('960px--');
  });

  it('leaves youtube unchanged', () => {
    const yt = 'https://www.youtube.com/watch?v=abc';
    expect(wikimediaVideoVariants(yt)).toBeNull();
    expect(playVideoSources(yt)).toEqual([{ src: yt }]);
  });
});
