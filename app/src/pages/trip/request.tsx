import { Box, Button, Flex, Input, Text, Textarea } from '@chakra-ui/react';
import { useState } from 'react';
import { postFeedback, tripRequestComment } from '../../api/feedback';
import { useTripLang, useTripText } from './use-trip';

/** "Going somewhere else?": ask for Trip prep for another country. Sent as feedback. */
export function TripRequestForm() {
  const t = useTripText();
  const lang = useTripLang();
  const [country, setCountry] = useState('');
  const [note, setNote] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

  const submit = async () => {
    if (!country.trim()) return;
    setState('sending');
    const ok = await postFeedback(tripRequestComment(country, note, lang));
    if (ok) {
      setCountry('');
      setNote('');
    }
    setState(ok ? 'sent' : 'error');
  };

  return (
    <Box bg="white" borderRadius="xl" p={4} borderWidth="1px" borderColor="primary.200" mt={4}>
      <Text fontSize="lg" fontWeight="700" color="primary.800">
        {t('trip_request_title', 'Going somewhere else?')}
      </Text>
      {state === 'sent' ? (
        <Text color="primary.800" mt={2}>
          {t('trip_request_thanks', 'Thanks, we have noted it. The countries asked for most come first.')}
        </Text>
      ) : (
        <Flex direction="column" gap={3} mt={2}>
          <Text color="primary.700" fontSize="sm">
            {t('trip_request_intro', 'Tell us which country you would like Trip prep for. The countries asked for most come first.')}
          </Text>
          <Input
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder={t('trip_request_country', 'Country')}
            maxLength={100}
            bg="white"
          />
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t('trip_request_note', 'When are you going? Anything else? (optional)')}
            maxLength={1000}
            bg="white"
          />
          {state === 'error' ? (
            <Text color="error.500" fontSize="sm">
              {t('trip_request_error', 'Your request could not be sent. Please try again.')}
            </Text>
          ) : null}
          <Button
            alignSelf="flex-end"
            colorPalette="primary"
            onClick={submit}
            disabled={!country.trim() || state === 'sending'}
            loading={state === 'sending'}
          >
            {t('trip_request_submit', 'Send request')}
          </Button>
        </Flex>
      )}
    </Box>
  );
}
