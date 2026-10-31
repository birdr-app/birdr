import {Box, Flex, Icon, Text} from "@chakra-ui/react"
import {motion} from "framer-motion"
import {FaCheckCircle, FaCheckSquare, FaHeart, FaHeartBroken, FaStar, FaTimesCircle} from "react-icons/fa"
import {useState, useEffect, useLayoutEffect, useRef} from "react"
import Confetti from "react-confetti"
import {FormattedMessage} from "react-intl"

const MEGA_CONFETTI_COLORS = [
  "#B9CC5E",
  "#3CC8E0",
  "#c09c5c",
  "#ac802e",
  "#1C7A4C",
  "#cc6600",
  "#fcd34d",
  "#fbbf24",
  "#f59e0b",
  "#eab308",
  "#d97706",
  "#8A4A12",
]

interface AnswerFeedbackProps {
  correct: boolean
  speciesFrequency?: string | null
  checklistAdded?: boolean
  checklistMissed?: boolean
  onAnimationComplete: () => void
}

const FEEDBACK_MS = 2000
const VAGRANT_FEEDBACK_MS = 2800
const CHECKLIST_EXTRA_MS = 700

export function isVagrantMega(correct: boolean, speciesFrequency?: string | null): boolean {
  return correct && speciesFrequency === "vagrant"
}

export function normalizeChecklistAdded(raw: unknown): boolean {
  return raw === true || raw === 1 || raw === 'true'
}

export function normalizeChecklistMissed(raw: unknown): boolean {
  return raw === true || raw === 1 || raw === 'true'
}

function ChecklistPill({
  visible,
  icon,
  messageId,
  defaultMessage,
  borderColor,
  textColor,
}: {
  visible: boolean
  icon: typeof FaCheckSquare
  messageId: string
  defaultMessage: string
  borderColor: string
  textColor: string
}) {
  if (!visible) return null

  return (
    <motion.div
      initial={{opacity: 0, y: 12, scale: 0.85}}
      animate={{opacity: 1, y: 0, scale: 1}}
      transition={{delay: 0.28, type: "spring", stiffness: 420, damping: 22}}
    >
      <Flex
        align="center"
        gap={2}
        mt={4}
        px={4}
        py={2}
        bg="white"
        borderRadius="full"
        borderWidth="2px"
        borderColor={borderColor}
        boxShadow="0 4px 14px rgba(0,0,0,0.12)"
        maxW="280px"
      >
        <Icon as={icon} boxSize={5} color={textColor} flexShrink={0} />
        <Text fontSize="sm" fontWeight="700" color={textColor} lineHeight="short">
          <FormattedMessage id={messageId} defaultMessage={defaultMessage} />
        </Text>
      </Flex>
    </motion.div>
  )
}

function ChecklistAddedBadge({visible}: {visible: boolean}) {
  return (
    <ChecklistPill
      visible={visible}
      icon={FaCheckSquare}
      messageId="checklist_added_toast"
      defaultMessage="Added to your checklist!"
      borderColor="success.400"
      textColor="success.700"
    />
  )
}

function ChecklistMissedBadge({visible}: {visible: boolean}) {
  return (
    <ChecklistPill
      visible={visible}
      icon={FaTimesCircle}
      messageId="checklist_missed_toast"
      defaultMessage="Missed it for your checklist!"
      borderColor="#d97706"
      textColor="#8A4A12"
    />
  )
}

export const AnswerFeedback = ({
                                 correct,
                                 speciesFrequency,
                                 checklistAdded = false,
                                 checklistMissed = false,
                                 onAnimationComplete,
                               }: AnswerFeedbackProps) => {
  const [heartState, setHeartState] = useState<"whole" | "broken">("whole")
  const hostRef = useRef<HTMLDivElement>(null)
  const [hostSize, setHostSize] = useState({width: 0, height: 0})
  const vagrantMega = isVagrantMega(correct, speciesFrequency)
  const showChecklistAdded = correct && checklistAdded
  const showChecklistMissed = !correct && checklistMissed
  const showChecklistPill = showChecklistAdded || showChecklistMissed
  const duration = vagrantMega
    ? VAGRANT_FEEDBACK_MS
    : showChecklistPill
      ? FEEDBACK_MS + CHECKLIST_EXTRA_MS
      : FEEDBACK_MS

  useLayoutEffect(() => {
    const el = hostRef.current
    if (!el) return
    const update = () => {
      setHostSize({width: el.clientWidth, height: el.clientHeight})
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [vagrantMega])

  useEffect(() => {
    if (!correct) {
      const interval = setInterval(() => {
        setHeartState("broken")
      }, 700)

      const done = setTimeout(() => {
        clearInterval(interval)
        setHeartState("whole")
        onAnimationComplete()
      }, duration)

      return () => {
        clearInterval(interval)
        clearTimeout(done)
      }
    }

    const done = setTimeout(onAnimationComplete, duration)
    return () => clearTimeout(done)
  }, [correct, duration, onAnimationComplete])

  return (
    <Box
      ref={hostRef}
      position="absolute"
      inset={0}
      display="flex"
      alignItems="center"
      justifyContent="center"
      zIndex={20}
      pointerEvents="none"
      overflow="hidden"
    >
      {vagrantMega && hostSize.width > 0 && (
        <Box position="absolute" inset={0} pointerEvents="none" aria-hidden zIndex={1}>
          <Confetti
            width={hostSize.width}
            height={hostSize.height}
            run={vagrantMega}
            recycle={false}
            numberOfPieces={90}
            initialVelocityY={20}
            initialVelocityX={10}
            gravity={0.32}
            friction={0.97}
            tweenDuration={8}
            colors={MEGA_CONFETTI_COLORS}
          />
        </Box>
      )}
      <motion.div
        initial={{opacity: 0}}
        animate={{opacity: 1}}
        exit={{opacity: 0}}
        style={{position: "relative", zIndex: 2, display: "flex", flexDirection: "column", alignItems: "center"}}
      >
        {correct ? (
          <motion.div
            initial={{scale: 0, y: -100}}
            animate={{
              scale: vagrantMega ? [0, 1.35, 1.15] : [0, 1.2, 1],
              y: [0, -20, 0],
            }}
            transition={{
              duration: 0.55,
              times: [0, 0.35, 1],
              ease: "easeOut",
            }}
          >
            <Box
              position="relative"
              textShadow="0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1), inset 0 2px 4px 0 rgba(0, 0, 0, 0.1)"
              display="flex"
              flexDirection="column"
              alignItems="center"
              justifyContent="center"
              backgroundColor="white"
              borderRadius={vagrantMega ? "xl" : "50%"}
              borderWidth={vagrantMega ? "2px" : undefined}
              borderColor={vagrantMega ? "#fcd34d" : undefined}
              p={vagrantMega ? 6 : 4}
              minW={vagrantMega ? "140px" : undefined}
            >
              {vagrantMega ? (
                <>
                  <Icon
                    as={FaStar}
                    boxSize={11}
                    color="#eab308"
                    position="relative"
                    zIndex={2}
                  />
                  <Text
                    fontSize="xl"
                    fontWeight="900"
                    letterSpacing="wider"
                    color="#8A4A12"
                    mt={2}
                  >
                    <FormattedMessage id="mega" defaultMessage="MEGA!" />
                  </Text>
                </>
              ) : (
                <Icon
                  as={FaCheckCircle}
                  boxSize={32}
                  color="success.500"
                  position="relative"
                  zIndex={2}
                />
              )}
            </Box>
          </motion.div>
        ) : (
          <motion.div
            animate={{
              x: [0, 20, -20, 20, -20, 0],
              rotate: [0, 10, -10, 10, 0, 0],
            }}
            transition={{
              duration: 0.5,
              repeat: 2,
              ease: "easeInOut",
            }}
          >
            <Box
              position="relative"
              width="160px"
              height="160px"
              borderRadius="50%"
              bg="white"
              boxShadow="0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1), inset 0 2px 4px 0 rgba(0, 0, 0, 0.1)"
              display="flex"
              alignItems="center"
              justifyContent="center"
              _before={{
                content: '""',
                position: "absolute",
                top: "2px",
                left: "2px",
                right: "2px",
                bottom: "2px",
                borderRadius: "50%",
                background:
                  "linear-gradient(to bottom, rgba(255,255,255,0.9), rgba(255,255,255,0.3))",
                zIndex: 1,
              }}
            >
              <Icon
                as={heartState === "whole" ? FaHeart : FaHeartBroken}
                boxSize={32}
                color="error.600"
                position="relative"
                zIndex={2}
              />
            </Box>
          </motion.div>
        )}
        <ChecklistAddedBadge visible={showChecklistAdded} />
        <ChecklistMissedBadge visible={showChecklistMissed} />
      </motion.div>
    </Box>
  )
}
