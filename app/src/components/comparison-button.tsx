import React, { useState } from "react";
import { createPortal } from "react-dom";
import {
  Box,
  Button,
  ButtonProps,
  Dialog,
  VStack,
  Text,
} from "@chakra-ui/react";
import { FormattedMessage } from "react-intl";
import { ComparisonContent } from "./comparison-content";

if (typeof document !== 'undefined') {
  const styleId = 'comparison-dialog-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .comparison-dialog-wrapper [role="dialog"],
      .comparison-dialog-wrapper [data-part="backdrop"],
      .comparison-dialog-wrapper [data-part="positioner"],
      .comparison-dialog-wrapper [data-part="content"] {
        z-index: 1400 !important;
      }
      .comparison-dialog-wrapper [data-part="backdrop"] {
        z-index: 1399 !important;
      }
      .comparison-dialog-wrapper [data-part="positioner"],
      .comparison-dialog-wrapper [data-part="content"] {
        z-index: 1401 !important;
      }
    `;
    document.head.appendChild(style);
  }
}

const DialogPositionerComponent = Dialog.Positioner as React.FC<any>;
const DialogContentComponent = Dialog.Content as React.FC<any>;
const DialogCloseTriggerComponent = Dialog.CloseTrigger as React.FC<any>;

type ComparisonButtonProps = {
  species1Id?: number;
  species2Id?: number;
  species1Name?: string;
  species2Name?: string;
  buttonLabel?: React.ReactNode;
  buttonProps?: ButtonProps;
  stopPropagation?: boolean;
};

export const ComparisonButton = ({
  species1Id,
  species2Id,
  species1Name,
  species2Name,
  buttonLabel = "Comparison",
  buttonProps,
  stopPropagation = false,
}: ComparisonButtonProps) => {
  const [isOpen, setIsOpen] = useState(false);

  const handleOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (stopPropagation) {
      event.stopPropagation();
    }
    if (!species1Id || !species2Id) {
      return;
    }
    setIsOpen(true);
  };

  const handleClose = (openState: boolean | { open: boolean }) => {
    const openValue = typeof openState === "boolean" ? openState : openState.open;
    setIsOpen(openValue);
  };

  const title = species1Name && species2Name
    ? `${species1Name} vs ${species2Name}`
    : "Species Comparison";

  return (
    <>
      <Button
        onClick={handleOpen}
        disabled={!species1Id || !species2Id}
        colorPalette="primary"
        variant="subtle"
        size="sm"
        {...buttonProps}
      >
        {buttonLabel}
      </Button>

      {isOpen && typeof document !== 'undefined' && createPortal(
        <Box className="comparison-dialog-wrapper">
          <Dialog.Root open={isOpen} onOpenChange={handleClose} modal={true}>
            <Dialog.Backdrop />
            <DialogPositionerComponent>
              <DialogContentComponent maxW="4xl" maxH="90vh" overflowY="auto">
                <Dialog.Header pr={10}>
                  <VStack align="start" gap={0}>
                    <Text fontWeight="bold" fontSize="lg">{title}</Text>
                  </VStack>
                </Dialog.Header>
                <DialogCloseTriggerComponent
                  position="absolute"
                  top={3}
                  right={3}
                  onClick={() => handleClose(false)}
                />
              <Dialog.Body>
                <ComparisonContent
                  species1Id={species1Id}
                  species2Id={species2Id}
                  species1Name={species1Name}
                  species2Name={species2Name}
                  onContributeClose={() => handleClose(false)}
                />
              </Dialog.Body>
              <Dialog.Footer>
                <Button onClick={() => handleClose(false)} colorPalette="primary">
                  Close
                </Button>
              </Dialog.Footer>
            </DialogContentComponent>
          </DialogPositionerComponent>
        </Dialog.Root>
        </Box>,
        document.body
      )}
    </>
  );
};
