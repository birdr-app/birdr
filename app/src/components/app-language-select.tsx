import { Box, Flex, Text } from "@chakra-ui/react";
import { useState } from "react";
import { FaLanguage } from "react-icons/fa";
import { APP_LOCALES, APP_LOCALE_LABELS, isAppLocale, type AppLocale } from "../i18n/app-locales";

type AppLanguageSelectProps = {
  value: string;
  onChange: (locale: AppLocale) => void;
  id?: string;
  variant?: "form" | "menu";
};

function localeLabel(value: string): string {
  return isAppLocale(value) ? APP_LOCALE_LABELS[value] : APP_LOCALE_LABELS.en;
}

export function AppLanguageSelect({
  value,
  onChange,
  id,
  variant = "form",
}: AppLanguageSelectProps) {
  if (variant === "menu") {
    return <MenuLanguageSelect value={value} onChange={onChange} />;
  }

  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value as AppLocale)}
      style={{
        width: "100%",
        minHeight: 40,
        paddingLeft: 12,
        paddingRight: 12,
        borderWidth: 1,
        borderStyle: "solid",
        borderColor: "var(--chakra-colors-gray-200, #e2e8f0)",
        borderRadius: 6,
        background: "white",
        fontSize: 16,
      }}
    >
      {APP_LOCALES.map((locale) => (
        <option key={locale} value={locale}>
          {APP_LOCALE_LABELS[locale]}
        </option>
      ))}
    </select>
  );
}

function MenuLanguageSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (locale: AppLocale) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = localeLabel(value);

  return (
    <Box>
      <Flex
        as="button"
        width="full"
        align="center"
        justify="space-between"
        gap={3}
        onClick={() => setOpen((currentOpen) => !currentOpen)}
        aria-expanded={open}
        aria-label={`App language, ${current}`}
        cursor="pointer"
        bg="transparent"
        borderWidth={0}
        p={0}
        textAlign="left"
      >
        <Flex align="center" gap={2} minW={0}>
          <Box color="gray.500" display="flex" flexShrink={0} aria-hidden>
            <FaLanguage size={18} />
          </Box>
          <Text fontSize="lg" color="gray.500">
            App language
          </Text>
        </Flex>
        <Text fontSize="lg" color="gray.700" whiteSpace="nowrap">
          {current}
          <Text as="span" color="gray.400" ml={1.5} aria-hidden>
            {open ? "▴" : "▾"}
          </Text>
        </Text>
      </Flex>
      {open ? (
        <Box mt={1} pl={7}>
          {APP_LOCALES.map((locale) => {
            const selected = value === locale;
            return (
              <Text
                key={locale}
                as="button"
                display="block"
                width="full"
                textAlign="left"
                py={1.5}
                fontSize="lg"
                fontWeight={selected ? "600" : "400"}
                color={selected ? "primary.700" : "gray.600"}
                _hover={{ color: "primary.800" }}
                cursor="pointer"
                bg="transparent"
                borderWidth={0}
                onClick={() => {
                  onChange(locale);
                  setOpen(false);
                }}
              >
                {APP_LOCALE_LABELS[locale]}
              </Text>
            );
          })}
        </Box>
      ) : null}
    </Box>
  );
}
