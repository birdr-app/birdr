import {
  resolvePlayMediaType,
  mediaSlotIndexFromQuestion,
} from '../core/question-media-index';
import { playMediaUrlFromQuestion, prefetchPlayMedia } from '../core/prefetch-play-media';
import { bindHtmlMediaCanPlay } from '../core/html-media-canplay';

describe('resolvePlayMediaType', () => {
  it('prefers question.media over game.media', () => {
    expect(
      resolvePlayMediaType({ media: 'audio', images: [], sounds: [] }, 'images')
    ).toBe('audio');
  });

  it('infers audio when only sounds are present (Club Mix Q11+)', () => {
    expect(
      resolvePlayMediaType(
        { images: [], videos: [], sounds: [{ url: 'https://x/a.mp3' }] },
        'images'
      )
    ).toBe('audio');
  });

  it('falls back to game media when arrays empty', () => {
    expect(resolvePlayMediaType({ images: [], sounds: [] }, 'video')).toBe('video');
  });
});

describe('mediaSlotIndexFromQuestion', () => {
  it('clamps to array bounds; play payloads use number 0', () => {
    expect(mediaSlotIndexFromQuestion({ number: 0 }, 1)).toBe(0);
    expect(mediaSlotIndexFromQuestion({ number: 11 }, 1)).toBe(0);
    expect(mediaSlotIndexFromQuestion({ number: null }, 3)).toBe(0);
  });
});

describe('playMediaUrlFromQuestion', () => {
  it('returns the current image url from a lean play payload', () => {
    expect(
      playMediaUrlFromQuestion({
        media: 'images',
        number: 0,
        images: [{ url: 'https://cdn.example/q1.jpg' }],
      })
    ).toEqual({ url: 'https://cdn.example/q1.jpg', kind: 'images' });
  });
});

describe('prefetchPlayMedia', () => {
  it('assigns image src so the browser starts fetching', () => {
    const srcs: string[] = [];
    const OriginalImage = global.Image;
    class FakeImage {
      set src(value: string) {
        srcs.push(value);
      }
    }
    (global as unknown as { Image: typeof Image }).Image = FakeImage as unknown as typeof Image;
    prefetchPlayMedia('https://cdn.example/q2.jpg', 'images');
    expect(srcs).toContain('https://cdn.example/q2.jpg');
    (global as unknown as { Image: typeof Image }).Image = OriginalImage;
  });
});

describe('bindHtmlMediaCanPlay', () => {
  it('calls back immediately when readyState is already HAVE_FUTURE_DATA', () => {
    const calls: number[] = [];
    bindHtmlMediaCanPlay(
      { getInternalPlayer: () => ({ readyState: 3 }) },
      () => calls.push(1)
    );
    expect(calls).toEqual([1]);
  });

  it('listens for canplay when the element is not buffered yet', () => {
    const listeners: Array<[string, () => void]> = [];
    const el = {
      readyState: 0,
      addEventListener: (name: string, cb: () => void) => listeners.push([name, cb]),
    };
    const calls: number[] = [];
    bindHtmlMediaCanPlay({ getInternalPlayer: () => el }, () => calls.push(1));
    expect(calls).toEqual([]);
    expect(listeners[0][0]).toBe('canplay');
    listeners[0][1]();
    expect(calls).toEqual([1]);
  });
});

