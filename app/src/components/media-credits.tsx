import { Box, Text, Link } from "@chakra-ui/react";
import { FormattedMessage } from "react-intl";
import { SpeciesImage, SpeciesVideo, SpeciesSound } from "../core/app-context";

type MediaItem = SpeciesImage | SpeciesVideo | SpeciesSound;

type MediaCreditsProps = {
  // Either pass a media object, or individual props
  media?: MediaItem;
  contributor?: string | null;
  source?: string | null;
  link?: string | null;
  fontSize?: string;
  color?: string;
  mt?: number | string;
  onClick?: () => void;
  /** During live play: explain that the original link appears after answering. */
  playHint?: boolean;
};

/**
 * Reusable component for displaying media credits (contributor and source link).
 * Used throughout the app to display consistent credit information for images, videos, and sounds.
 * 
 * Usage:
 *   <MediaCredits media={video} mt={2} />
 *   or
 *   <MediaCredits contributor={contributor} source={source} link={link} />
 */
export function MediaCredits({
  media,
  contributor: contributorProp,
  source: sourceProp,
  link: linkProp,
  fontSize = "sm",
  color = "gray.600",
  mt,
  onClick,
  playHint = false,
}: MediaCreditsProps) {
  // Extract values from media object if provided, otherwise use individual props
  const contributor = media?.contributor ?? contributorProp;
  const source = media?.source ?? sourceProp;
  const link = media?.link ?? linkProp;
  const hint = playHint ? (
    <Text fontSize="xs" color="gray.500" mt={1}>
      {link ? (
        <FormattedMessage
          id="credits_click_to_see"
          defaultMessage="Click the link to see the original."
        />
      ) : (
        <FormattedMessage
          id="credits_link_after_answer"
          defaultMessage="After answering you'll get the link to the original."
        />
      )}
    </Text>
  ) : null;
  // If no contributor and no link, don't render anything
  if (!contributor && !link) {
    return hint;
  }

  const creditsLine = !contributor && link ? (
    <Text fontSize={fontSize} color={color}>
      <Link
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        color="primary.600"
        onClick={onClick}
      >
        {source || 'Source'}
      </Link>
    </Text>
  ) : (
    <Text fontSize={fontSize} color={color}>
      {contributor}
      {link && (
        <>
          {' / '}
          <Link
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            color="primary.600"
            onClick={onClick}
          >
            {source || 'Source'}
          </Link>
        </>
      )}
    </Text>
  );

  if (!hint) {
    return (
      <Box mt={mt}>
        {creditsLine}
      </Box>
    );
  }

  return (
    <Box mt={mt}>
      {creditsLine}
      {hint}
    </Box>
  );
}

