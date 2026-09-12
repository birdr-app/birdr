import {useContext, type ComponentType, type ReactNode} from "react";
import AppContext from "../core/app-context";
import {Box, Flex, Heading, RadioCard, Switch} from "@chakra-ui/react";
import {FormattedMessage} from "react-intl";

/** Chakra RadioCard slot typings omit `children` / conflict with Ark props; runtime is fine. */
const RcItem = RadioCard.Item as unknown as ComponentType<{
  value: string;
  w?: string;
  children?: ReactNode;
}>;
const RcItemText = RadioCard.ItemText as unknown as ComponentType<{
  children?: ReactNode;
}>;

const SwLabel = Switch.Label as unknown as ComponentType<{
  children?: ReactNode;
}>;

export const SelectMediaType = () => {
  const {mediaType, setMediaType, soundsScope, setSoundsScope} = useContext(AppContext);

  const onChange = (value: string) => {
    setMediaType && setMediaType(value);
    if (value !== "audio") {
      setSoundsScope && setSoundsScope("all");
    }
  };

  return (
    <Box>
      <Heading size={"md"} mb={4}>
        <FormattedMessage id={"media type"} defaultMessage={"Media type"} />
      </Heading>
      <RadioCard.Root
        colorPalette="primary"
        variant="surface"
        size="md"
        value={mediaType}
        onValueChange={(details: { value: string | null }) =>
          details.value && onChange(details.value)}
        w="100%"
      >
        <Box display="flex" flexDirection={['column', 'row']} gap={4}>
          <RcItem value="images" w="100%">
            <RadioCard.ItemHiddenInput />
            <RadioCard.ItemControl>
              <RadioCard.ItemContent>
                <RcItemText>
                  <FormattedMessage id={"pictures"} defaultMessage={"Pictures"} />
                </RcItemText>
              </RadioCard.ItemContent>
              <RadioCard.ItemIndicator />
            </RadioCard.ItemControl>
          </RcItem>
          <RcItem value="audio" w="100%">
            <RadioCard.ItemHiddenInput />
            <RadioCard.ItemControl>
              <RadioCard.ItemContent>
                <RcItemText>
                  <FormattedMessage id={"sounds"} defaultMessage={"Sounds"} />
                  {mediaType === "audio" && (
                    <Flex align="center" gap={3} pt={4}>
                      <Switch.Root
                        colorPalette="primary"
                        checked={soundsScope === "passerines"}
                        onCheckedChange={(details: { checked: boolean }) =>
                          setSoundsScope?.(details.checked ? "passerines" : "all")}
                      >
                        <Switch.HiddenInput />
                        <Switch.Control />
                        <SwLabel>
                          <FormattedMessage
                            id="passerines only"
                            defaultMessage="Passerines only"
                          />
                        </SwLabel>
                      </Switch.Root>
                    </Flex>
                  )}
                </RcItemText>
              </RadioCard.ItemContent>
              <RadioCard.ItemIndicator />
            </RadioCard.ItemControl>
          </RcItem>
          <RcItem value="video" w="100%">
            <RadioCard.ItemHiddenInput />
            <RadioCard.ItemControl>
              <RadioCard.ItemContent>
                <RcItemText>
                  <Flex as="span" align="center" gap={2} wrap="wrap">
                    <FormattedMessage id={"videos"} defaultMessage={"Videos"} />
                    <Box
                      as="span"
                      fontSize="2xs"
                      fontWeight="700"
                      letterSpacing="wider"
                      textTransform="uppercase"
                      px="1.5"
                      py="0.5"
                      borderRadius="sm"
                      bg="primary.100"
                      color="primary.700"
                    >
                      <FormattedMessage id="beta" defaultMessage="Beta" />
                    </Box>
                  </Flex>
                </RcItemText>
              </RadioCard.ItemContent>
              <RadioCard.ItemIndicator />
            </RadioCard.ItemControl>
          </RcItem>
        </Box>
      </RadioCard.Root>
    </Box>
  );
};
