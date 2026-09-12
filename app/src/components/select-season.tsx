import {Box, Heading, RadioCard} from "@chakra-ui/react";
import {useContext, type ComponentType, type ReactNode} from "react";
import AppContext from "../core/app-context";
import {FormattedMessage} from "react-intl";

const RcItem = RadioCard.Item as unknown as ComponentType<{
  value: string;
  w?: string;
  children?: ReactNode;
}>;
const RcItemText = RadioCard.ItemText as unknown as ComponentType<{
  children?: ReactNode;
}>;

export const SEASON_OPTIONS: {
  value: string;
  titleId: string;
  titleDefault: string;
}[] = [
  { value: '', titleId: 'season_all_year', titleDefault: 'All year' },
  { value: 'spring', titleId: 'season_spring', titleDefault: 'Spring' },
  { value: 'summer', titleId: 'season_summer', titleDefault: 'Summer' },
  { value: 'autumn', titleId: 'season_autumn', titleDefault: 'Autumn' },
  { value: 'winter', titleId: 'season_winter', titleDefault: 'Winter' },
];

const SelectSeason = () => {
  const { season, setSeason } = useContext(AppContext);

  return (
    <Box>
      <Heading size={'md'} mb={4}>
        <FormattedMessage id={'season'} defaultMessage={'Season'} />
      </Heading>
      <RadioCard.Root
        colorPalette="primary"
        variant="surface"
        size="md"
        value={season || ''}
        onValueChange={(details: { value: string | null }) => {
          setSeason?.(details.value || '');
        }}
      >
        <Box display="flex" flexWrap="wrap" gap={3}>
          {SEASON_OPTIONS.map((opt) => (
            <RcItem key={opt.value || 'all'} value={opt.value} w="auto">
              <RadioCard.ItemHiddenInput />
              <RadioCard.ItemControl>
                <RcItemText>
                  <FormattedMessage id={opt.titleId} defaultMessage={opt.titleDefault} />
                </RcItemText>
              </RadioCard.ItemControl>
            </RcItem>
          ))}
        </Box>
      </RadioCard.Root>
    </Box>
  );
};

export default SelectSeason;
