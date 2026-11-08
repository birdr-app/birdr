import AppContext from "../../../core/app-context"
import {
  Alert,
  Button, Flex,
  Dialog,
  Textarea,
  VStack
} from "@chakra-ui/react"
import {FormattedMessage, useIntl} from "react-intl"
import {useContext, useEffect, useState} from "react"
import { toaster } from "@/components/ui/toaster"
import { apiUrl } from "../../../api/baseUrl"

const {
  Root: DialogRoot,
  Backdrop: DialogBackdrop,
  Positioner: DialogPositioner,
  Content: DialogContent,
  Header: DialogHeader,
  Body: DialogBody,
  Footer: DialogFooter,
  CloseTrigger: DialogCloseTrigger,
} = Dialog


type MediaInfo = {
  id?: number
  type?: 'image' | 'video' | 'audio' // Made optional since type doesn't matter for the API
  url?: string
  link?: string | null
  contributor?: string | null
  index?: number
}

type Approval = {
  approved_by: string
  approved_at: string
}

type Props = {
  isOpen: boolean
  onClose: () => void
  media?: MediaInfo | null
  onSuccess?: () => void // Callback to execute after successful flagging
  /** When true, submit as MediaReview (rejected) instead of FlagMedia. Use for game-question flagging. */
  useMediaReview?: boolean
}

export const FlagMedia = ({isOpen, onClose, media, onSuccess, useMediaReview = false}: Props) => {
  const [message, setMessage] = useState<string>('')

  const intl = useIntl()
  const {player} = useContext(AppContext)

  const [approval, setApproval] = useState<Approval | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setMessage('')
    }
  }, [isOpen])

  // Warn before overruling someone else's approval of this media.
  useEffect(() => {
    setApproval(null)
    if (!isOpen || !media?.id) return
    let cancelled = false
    const params = player?.token ? `?player_token=${encodeURIComponent(player.token)}` : ''
    fetch(apiUrl(`/api/media/${media.id}/approval/${params}`))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data?.approved) {
          setApproval({approved_by: data.approved_by, approved_at: data.approved_at})
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [isOpen, media?.id, player?.token])

  const onSubmit = async () => {
    const description = message.trim() || (useMediaReview ? 'Flagged from game' : '')

    if (!media?.id) {
      toaster.create({
        title: intl.formatMessage({id:"problem flagging", defaultMessage: "Error flagging."}),
        description: "Media ID is required to flag media.",
        colorPalette: "error",
        duration: 4000,
        isClosable: true,
      })
      onClose()
      return
    }
    
    const url = useMediaReview ? apiUrl('/api/review-media/') : apiUrl('/api/flag-media/')
    const body = useMediaReview
      ? {
          media_id: media.id,
          player_token: player?.token,
          review_type: 'rejected' as const,
          description,
        }
      : {
          media_id: media.id,
          player_token: player?.token,
          description,
        }
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body),
    })
    const successMessage = intl.formatMessage({id:"media flagged", defaultMessage: "Media flagged. We'll look into this."})
    const errorMessage = intl.formatMessage({id:"problem flagging", defaultMessage: "Error flagging."})
    
    if (response.status === 201) {
      toaster.create({
        title: successMessage,
        colorPalette: "success",
        duration: 4000,
        isClosable: true,
      });
      // Call onSuccess callback if provided (e.g., to advance to next question)
      if (onSuccess) {
        onSuccess();
      }
    } else {
      toaster.create({
        title: errorMessage,
        colorPalette: "error",
        duration: 4000,
        isClosable: true,
      })
    }
    onClose()
  }

  return (
    <DialogRoot open={isOpen} onOpenChange={(e: { open: boolean }) => {
      if (!e.open) {
        onClose()
      }
    }}>
      <DialogBackdrop />
      <DialogPositioner>
        <DialogContent>
          <DialogCloseTrigger />
          <DialogHeader>
            <FormattedMessage id={'flag media title'} defaultMessage={'Flag media'}/>
          </DialogHeader>
          <DialogBody>
            <VStack gap={4} align="stretch">
              {approval && (
                <Alert.Root status="warning">
                  <Alert.Indicator />
                  <Alert.Title>
                    <FormattedMessage
                      id={'flag approved warning'}
                      defaultMessage={'This picture was approved by {name} on {date}. Are you sure you want to flag this?'}
                      values={{
                        name: approval.approved_by,
                        date: intl.formatDate(approval.approved_at, {day: 'numeric', month: 'short', year: 'numeric'}),
                      }}
                    />
                  </Alert.Title>
                </Alert.Root>
              )}
              <FormattedMessage
                id={'flag modal description'}
                defaultMessage={'Can you tell us what was wrong with this media?'}
              />
              <Textarea
                cursor="text"
                value={message}
                onChange={(val) => setMessage(val.currentTarget.value)}
                placeholder={intl.formatMessage({
                  id: 'flag description',
                  defaultMessage: 'Description'
                }) as string}
                rows={4}
              />
            </VStack>
          </DialogBody>
          <DialogFooter>
            <Flex justifyContent={'space-between'} width={'full'}>
              <Button onClick={onClose} colorPalette="primary">
                <FormattedMessage defaultMessage={'Cancel'} id='cancel'/>
              </Button>
              <Button onClick={onSubmit} colorPalette="primary">
                <FormattedMessage defaultMessage={'Flag'} id='flag'/>
              </Button>
            </Flex>
          </DialogFooter>
        </DialogContent>
      </DialogPositioner>
    </DialogRoot>
  )

}
