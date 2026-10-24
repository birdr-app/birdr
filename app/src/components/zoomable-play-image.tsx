import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  Dialog,
  Image,
  Portal,
  Flex,
} from "@chakra-ui/react";
import { FormattedMessage, useIntl } from "react-intl";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

/** Same height for every in-game photo so questions don't jump. ~400px on a typical laptop. */
export const PLAY_IMAGE_STAGE_HEIGHT = "clamp(240px, 45vh, 480px)";

export type ZoomablePlayImageProps = {
  previewSrc: string;
  /** Higher-resolution URL for the full-screen viewer (pinch / zoom) */
  fullSrc: string;
  onLoad: () => void;
  onError: (e: React.SyntheticEvent<HTMLImageElement, Event>) => void;
};

/**
 * Inline question image with click-to-open full screen and pinch / pan / double-tap reset (web).
 */
export function ZoomablePlayImage({
  previewSrc,
  fullSrc,
  onLoad,
  onError,
}: ZoomablePlayImageProps) {
  const [open, setOpen] = useState(false);
  const intl = useIntl();
  // Wikimedia answers 429 when it is busy generating thumbnails. Try the other
  // standard size once (often already cached) before giving up on the image.
  const [src, setSrc] = useState(previewSrc);
  useEffect(() => setSrc(previewSrc), [previewSrc]);
  const handleError = (e: React.SyntheticEvent<HTMLImageElement, Event>) => {
    if (src === previewSrc && fullSrc && fullSrc !== previewSrc) {
      setSrc(fullSrc);
      return;
    }
    onError(e);
  };

  return (
    <>
      <Box
        w="100%"
        h={PLAY_IMAGE_STAGE_HEIGHT}
        bg="transparent"
        overflow="hidden"
        display="flex"
        alignItems="center"
        justifyContent="center"
        cursor="pointer"
        onClick={() => setOpen(true)}
        title={intl.formatMessage({
          id: "tap_image_fullscreen",
          defaultMessage: "Click to open full screen — pinch or scroll wheel to zoom",
        })}
      >
        <Image
          src={src}
          onLoad={onLoad}
          onError={handleError}
          w="100%"
          h="100%"
          objectFit="contain"
          bg="transparent"
          pointerEvents="none"
        />
      </Box>
      <Dialog.Root
        open={open}
        onOpenChange={(e: { open: boolean }) => !e.open && setOpen(false)}
        size="full"
      >
        <Portal>
          <Dialog.Backdrop bg="blackAlpha.900" />
          <Dialog.Positioner display="flex" alignItems="center" justifyContent="center" p={0}>
            <Dialog.Content
              maxW="100vw"
              maxH="100vh"
              w="100vw"
              h="100vh"
              m={0}
              rounded="none"
              bg="transparent"
              borderWidth={0}
              shadow="none"
              display="flex"
              flexDirection="column"
            >
              <Dialog.Header flexShrink={0} borderBottomWidth={0} py={3} px={4}>
                <Flex justify="flex-end" align="center" gap={3} w="100%">
                  <Button
                    size="sm"
                    variant="outline"
                    colorPalette="gray"
                    borderColor="whiteAlpha.500"
                    color="white"
                    onClick={() => setOpen(false)}
                  >
                    <FormattedMessage id="close" defaultMessage="Close" />
                  </Button>
                  <Dialog.CloseTrigger color="white" />
                </Flex>
              </Dialog.Header>
              <Dialog.Body
                flex="1"
                p={0}
                overflow="hidden"
                display="flex"
                alignItems="center"
                justifyContent="center"
              >
                <Box w="100%" h="100%" px={2} pb={4}>
                  <TransformWrapper
                    initialScale={1}
                    minScale={1}
                    maxScale={5}
                    centerOnInit
                    doubleClick={{ mode: "reset" }}
                  >
                    <TransformComponent
                      wrapperStyle={{ width: "100%", height: "100%", maxHeight: "calc(100vh - 5rem)" }}
                      contentStyle={{
                        width: "100%",
                        height: "100%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {open ? (
                        <img
                          src={fullSrc}
                          alt=""
                          style={{
                            maxWidth: "100%",
                            maxHeight: "calc(100vh - 5rem)",
                            objectFit: "contain",
                          }}
                          onError={(e) => {
                            e.currentTarget.src = "/images/birdr-logo.png";
                          }}
                        />
                      ) : null}
                    </TransformComponent>
                  </TransformWrapper>
                </Box>
              </Dialog.Body>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </>
  );
}
