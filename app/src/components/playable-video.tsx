import React from 'react';
import ReactPlayer from 'react-player';
import { FormattedMessage } from 'react-intl';
import {
  isAppleTouchDevice,
  isWikimediaVideoUrl,
  playVideoSources,
  playVideoStillUrl,
} from '../utils/play-video-url';

type PlayableVideoProps = {
  url: string;
  playing?: boolean;
  controls?: boolean;
  width?: string | number;
  height?: string | number;
  onReady?: () => void;
};

const STILL_FALLBACK_MS = 5000;

/**
 * Commons files: native video, trying device-friendly transcodes then a JPEG still.
 * YouTube and other hosts keep ReactPlayer.
 */
export function PlayableVideo({
  url,
  playing = false,
  controls = true,
  width = '100%',
  height,
  onReady,
}: PlayableVideoProps) {
  if (isWikimediaVideoUrl(url)) {
    return (
      <WikimediaPlayableVideo
        url={url}
        playing={playing}
        controls={controls}
        width={width}
        height={height}
        onReady={onReady}
      />
    );
  }

  return (
    <ReactPlayer
      url={url}
      controls={controls}
      playing={playing}
      width={width}
      height={height ?? '50%'}
      onReady={onReady}
    />
  );
}

function WikimediaPlayableVideo({
  url,
  playing,
  controls,
  width,
  height,
  onReady,
}: PlayableVideoProps) {
  const still = playVideoStillUrl(url);
  const sources = React.useMemo(() => playVideoSources(url), [url]);
  const [sourceIndex, setSourceIndex] = React.useState(0);
  const [showStill, setShowStill] = React.useState(false);
  const readyRef = React.useRef(false);
  const onReadyRef = React.useRef(onReady);
  onReadyRef.current = onReady;

  React.useEffect(() => {
    readyRef.current = false;
    setSourceIndex(0);
    setShowStill(false);
  }, [url]);

  const notifyReady = React.useCallback(() => {
    readyRef.current = true;
    onReadyRef.current?.();
  }, []);

  const failOver = React.useCallback(() => {
    if (readyRef.current || showStill) return;
    if (sourceIndex + 1 < sources.length) {
      setSourceIndex((index) => index + 1);
      return;
    }
    if (still) {
      setShowStill(true);
      return;
    }
    onReadyRef.current?.();
  }, [showStill, sourceIndex, sources.length, still]);

  React.useEffect(() => {
    if (showStill || !still || !isAppleTouchDevice()) return;
    const timer = window.setTimeout(() => {
      if (!readyRef.current) failOver();
    }, STILL_FALLBACK_MS);
    return () => window.clearTimeout(timer);
  }, [url, sourceIndex, showStill, still, failOver]);

  const frameStyle: React.CSSProperties = {
    position: 'relative',
    width: typeof width === 'number' ? `${width}px` : width,
    height: height == null ? 'auto' : typeof height === 'number' ? `${height}px` : height,
    maxWidth: '100%',
    background: '#000',
    overflow: 'hidden',
  };

  if (showStill && still) {
    return (
      <div style={frameStyle}>
        <img
          src={still}
          alt=""
          onLoad={notifyReady}
          onError={notifyReady}
          style={{
            width: '100%',
            height: height == null ? 'auto' : '100%',
            objectFit: 'contain',
            display: 'block',
            background: '#000',
          }}
        />
        <p style={disclaimerStyle}>
          <FormattedMessage
            id="video_still_fallback"
            defaultMessage="This video couldn't be played. Showing a still instead."
          />
        </p>
      </div>
    );
  }

  const current = sources[sourceIndex] ?? sources[0];

  return (
    <video
      key={current?.src}
      src={current?.src}
      controls={controls}
      autoPlay={playing}
      playsInline
      preload="metadata"
      poster={still ?? undefined}
      width="100%"
      style={frameStyle}
      onLoadedData={notifyReady}
      onError={failOver}
    />
  );
}

const disclaimerStyle: React.CSSProperties = {
  position: 'absolute',
  left: 0,
  right: 0,
  bottom: 0,
  margin: 0,
  padding: '6px 8px',
  fontSize: 12,
  lineHeight: 1.35,
  textAlign: 'center',
  color: '#fff',
  background: 'rgba(0, 0, 0, 0.65)',
};
