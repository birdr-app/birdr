import { Image, type ImageProps } from '@chakra-ui/react';
import { useContext } from 'react';
import AppContext from '../core/app-context';
import { DEFAULT_VISUAL_STYLE, birdrImage, showsGameArt } from '../user/visual-style';

type Props = Omit<ImageProps, 'src'> & { filename: string };

export function BirdrArtImage({ filename, ...rest }: Props) {
  const { visualStyle } = useContext(AppContext);
  if (!showsGameArt(visualStyle)) return null;
  return <Image src={birdrImage(filename, visualStyle ?? DEFAULT_VISUAL_STYLE)} {...rest} />;
}
