import { Box, Button, Dialog, Flex, Text, Textarea } from '@chakra-ui/react';
import { useState } from 'react';
import { postFeedback } from '../api/feedback';

const { Root, Backdrop, Positioner, Content, Header, Body, CloseTrigger } = Dialog;

const TEXTS = {
  en: {
    label: 'Under construction!',
    link: 'What do you think?',
    cancel: 'Cancel',
    title: 'Nice that you are trying this out!',
    intro: 'This feature is still in development. Do you like this? Let us know what you think, what is missing or what goes wrong.',
    placeholder: 'Your feedback',
    send: 'Send feedback',
    thanks: 'Thanks! We read every message.',
    error: 'Your feedback could not be sent. Please try again.',
    close: 'Close',
  },
  nl: {
    label: 'In aanbouw!',
    link: 'Wat vind je ervan?',
    cancel: 'Annuleren',
    title: 'Leuk dat je dit uitprobeert!',
    intro: 'Deze functie is nog in ontwikkeling. Vind je dit leuk? Laat ons weten wat je ervan vindt, wat er ontbreekt of wat misgaat.',
    placeholder: 'Jouw feedback',
    send: 'Feedback versturen',
    thanks: 'Bedankt! We lezen elk bericht.',
    error: 'Je feedback kon niet worden verstuurd. Probeer het opnieuw.',
    close: 'Sluiten',
  },
};

/** Yellow warning triangle with an exclamation mark. */
function WarningIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d="M12 2.5 22.5 21h-21z" fill="#FACC15" stroke="#CA8A04" strokeWidth="1.5" strokeLinejoin="round" />
      <rect x="11" y="9" width="2" height="6.5" rx="1" fill="#422006" />
      <circle cx="12" cy="18" r="1.2" fill="#422006" />
    </svg>
  );
}

/** "Under construction" link that opens a dialog asking for feedback on a new feature. */
export function UnderConstruction({ feature, lang = 'en' }: { feature: string; lang?: string }) {
  const t = TEXTS[lang === 'nl' ? 'nl' : 'en'];
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

  const submit = async () => {
    if (!note.trim()) return;
    setState('sending');
    const ok = await postFeedback(`Feedback on ${feature} (under construction)\n\n${note.trim()}\n\n(app language: ${lang})`);
    if (ok) setNote('');
    setState(ok ? 'sent' : 'error');
  };

  return (
    <>
      <Flex align="center" gap={1} alignSelf="flex-start" fontSize="sm" fontWeight="600" color="orange.700" wrap="wrap">
        <WarningIcon />
        <span>{t.label}</span>
        <Box
          as="button"
          onClick={() => {
            setState('idle');
            setOpen(true);
          }}
          textDecoration="underline"
          cursor="pointer"
        >
          {t.link}
        </Box>
      </Flex>
      <Root open={open} onOpenChange={(e: { open: boolean }) => setOpen(e.open)} placement="center">
        <Backdrop />
        <Positioner>
          <Content mx={4}>
            <Header>
              <Text fontWeight="700" fontSize="lg">
                {t.title}
              </Text>
            </Header>
            <Body pb={5}>
              <Flex direction="column" gap={3}>
                <Text>{t.intro}</Text>
                {state === 'sent' ? (
                  <Text color="primary.800" fontWeight="600">
                    {t.thanks}
                  </Text>
                ) : (
                  <>
                    <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder={t.placeholder} maxLength={1000} rows={5} />
                    {state === 'error' ? (
                      <Text color="error.500" fontSize="sm">
                        {t.error}
                      </Text>
                    ) : null}
                    <Flex justify="flex-end" gap={2}>
                      <Button variant="outline" onClick={() => setOpen(false)}>
                        {t.cancel}
                      </Button>
                      <Button colorPalette="primary" onClick={submit} disabled={!note.trim() || state === 'sending'} loading={state === 'sending'}>
                        {t.send}
                      </Button>
                    </Flex>
                  </>
                )}
              </Flex>
            </Body>
            <CloseTrigger />
          </Content>
        </Positioner>
      </Root>
    </>
  );
}
