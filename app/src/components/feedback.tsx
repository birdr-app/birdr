import {Box, Button, CardRoot, Flex, Heading, Icon, Link, Textarea} from "@chakra-ui/react"
import {FormattedMessage, useIntl} from "react-intl"
import {useState} from "react"
import { FaChevronDown, FaChevronRight, FaComment } from "react-icons/fa"
import { toaster } from "@/components/ui/toaster"
import { apiUrl } from "../api/baseUrl"
import { authService } from "../api/services/auth.service"

export const Feedback = () => {
  const intl = useIntl()
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [open, setOpen] = useState(false);

  const submit = async () => {
    if (!comment.trim()) return;
    setSubmitting(true);
    const player_token = localStorage.getItem('player-token');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    const accessToken = authService.getAccessToken();
    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }
    const response = await fetch(apiUrl('/api/feedback/'), {
      method: 'POST',
      headers,
      body: JSON.stringify({
        comment: comment.trim(),
        ...(player_token ? { player_token } : {}),
      }),
    })
    setSubmitting(false);

    if (response.ok) {
      setSubmitted(true)
      setComment('')
      toaster.create({
        title: intl.formatMessage({id: 'thanks', defaultMessage: 'Thanks!'}),
        description: intl.formatMessage({id: 'thanks for your feedback message', defaultMessage: 'Thank you for your feedback!'}),
        colorPalette: "success",
        duration: 3000,
        isClosable: true,
      })
      setTimeout(() => {
        setSubmitted(false)
        setOpen(false)
      }, 3000)
    } else {
      toaster.create({
        title: intl.formatMessage({id: 'error', defaultMessage: 'Error'}),
        description: intl.formatMessage({id: 'error submitting feedback', defaultMessage: 'Failed to submit feedback. Please try again.'}),
        colorPalette: "error",
        duration: 4000,
        isClosable: true,
      })
    }
  }

  return (
    <Box id="feedback" w="full">
      <Link
        as="button"
        type="button"
        onClick={() => setOpen((value) => !value)}
        color="primary.500"
        fontWeight="600"
        fontSize="md"
        display="inline-flex"
        alignItems="center"
        gap={2}
        textAlign="left"
        cursor="pointer"
        textDecoration="none"
        _hover={{ textDecoration: "underline" }}
        aria-expanded={open}
      >
        <Icon as={FaComment} boxSize={4} aria-hidden />
        <FormattedMessage id={'feedback'} defaultMessage={'Feedback & contact'}/>
        <Icon as={open ? FaChevronDown : FaChevronRight} boxSize={3} aria-hidden />
      </Link>
      {open ? (
        <CardRoot
          mt={3}
          border={"1px solid"}
          shadow={'lg'}
          borderColor={'gray.300'}
          backgroundColor={submitted ? 'primary.100' : undefined}
          borderRadius='8px'
          p={8}
        >
          <Flex direction={'column'} gap={4}>
            {submitted ? (
              <>
                <Heading size={'md'} color={'primary.500'}>
                  <FormattedMessage id={'thanks'} defaultMessage={'Thanks!'}/>
                </Heading>
                <FormattedMessage id={'thanks for your feedback message'} defaultMessage={'Thank you for your feedback!'}/>
              </>
            ) : (
              <>
                <FormattedMessage
                  id={'feedback invite'}
                  defaultMessage={'Found a bug or want to share something positive? We would love to hear from you.'}
                />
                <Textarea
                  cursor="text"
                  value={comment}
                  onChange={(val) => setComment(val.target.value)}
                  placeholder={intl.formatMessage({ id: 'your feedback placeholder', defaultMessage: 'Your feedback...' })}
                />
                <Box alignSelf="flex-end">
                  <Button
                    onClick={submit}
                    disabled={!comment.trim() || submitting}
                    loading={submitting}
                    colorPalette="primary"
                  >
                    <FormattedMessage id={'submit'} defaultMessage={'Submit'}/>
                  </Button>
                </Box>
              </>
            )}
          </Flex>
        </CardRoot>
      ) : null}
    </Box>
  )
}
