/** Default media stage heights — keep in sync with QuestionMediaView imageFrame / videoFrame. */
export const QUESTION_IMAGE_HEIGHT = 280;
export const QUESTION_VIDEO_HEIGHT = 220;
export const QUESTION_AUDIO_CONTROL_HEIGHT = 56;

/** iPad and other wide play layouts. Phones keep QUESTION_IMAGE_HEIGHT. */
export const WIDE_PLAY_MIN_WIDTH = 600;
export const WIDE_PLAY_MEDIA_HEIGHT_RATIO = 0.5;

export function widePlayMediaHeight(screenWidth: number, screenHeight: number): number | undefined {
  if (screenWidth < WIDE_PLAY_MIN_WIDTH) return undefined;
  return Math.round(screenHeight * WIDE_PLAY_MEDIA_HEIGHT_RATIO);
}

export type QuestionMediaType = 'images' | 'video' | 'audio';

export function questionMediaStageHeight(
  mediaType: QuestionMediaType,
  options?: { imageHeight?: number; videoHeight?: number }
): number {
  if (mediaType === 'video') {
    return options?.videoHeight ?? QUESTION_VIDEO_HEIGHT;
  }
  if (mediaType === 'audio') {
    return QUESTION_AUDIO_CONTROL_HEIGHT;
  }
  return options?.imageHeight ?? QUESTION_IMAGE_HEIGHT;
}

/** Total vertical space for the media stage (credits/flag sit on top of the picture). */
export function questionMediaBlockHeight(
  mediaType: QuestionMediaType,
  options?: { imageHeight?: number; videoHeight?: number }
): number {
  return questionMediaStageHeight(mediaType, options);
}
