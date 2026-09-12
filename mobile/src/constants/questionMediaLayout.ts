/** Default media stage heights — keep in sync with QuestionMediaView imageFrame / videoFrame. */
export const QUESTION_IMAGE_HEIGHT = 280;
export const QUESTION_VIDEO_HEIGHT = 220;
export const QUESTION_AUDIO_CONTROL_HEIGHT = 56;

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
