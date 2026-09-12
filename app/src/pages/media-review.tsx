import { useState, useEffect, useContext, useCallback, useMemo, useRef } from 'react';
import {
  Badge,
  Box,
  Flex,
  Heading,
  Image,
  Button,
  Dialog,
  Text,
  SimpleGrid,
  Icon,
  Select,
  Spinner,
  Portal,
  createListCollection,
  ListRoot,
  ListItem,
} from '@chakra-ui/react';
import { Page } from '../shared/components/layout';
import { FormattedMessage, useIntl } from 'react-intl';
import AppContext from '../core/app-context';
import type { Species } from '../core/app-context';
import { MediaServiceImpl, MediaItem, SpeciesWithMedia, SpeciesReviewStatsResponse, type ReviewLevel } from '../api/services/media.service';
import SpeciesCombobox from '../components/species-combobox';
import { ApiClient, apiClient } from '../api/client';
import { authService } from '../api/services/auth.service';
import { toaster } from '@/components/ui/toaster';
import { BsCheckCircle, BsXCircle } from 'react-icons/bs';
import { UseCountries } from '../user/use-countries';
import CountryCombobox from '../components/country-combobox';
import { useParams, useSearchParams } from 'react-router-dom';
import { fetchSpeciesDetail } from '../api/fetch-species-detail';
import { FaArrowAltCircleRight, FaChevronDown, FaChevronRight, FaTrophy } from "react-icons/fa";
import { FaQuestion } from "react-icons/fa";
import Confetti from "react-confetti";
import { keyframes } from "@emotion/react";

const {
  Root: DialogRoot,
  Backdrop: DialogBackdrop,
  Positioner: DialogPositioner,
  Content: DialogContent,
  Header: DialogHeader,
  Body: DialogBody,
  CloseTrigger: DialogCloseTrigger,
} = Dialog;

const mediaService = new MediaServiceImpl(apiClient);

/** not_sure counts as rejected for display and overlays. */
function effectiveReviewType(
  raw: 'approved' | 'rejected' | 'not_sure' | null | undefined
): 'approved' | 'rejected' | undefined {
  if (raw == null) return undefined;
  if (raw === 'approved') return 'approved';
  return 'rejected';
}

function deltaSpeciesReviewCounts(
  prevType: 'approved' | 'rejected' | 'not_sure' | null,
  nextType: 'approved' | 'rejected' | 'not_sure',
  cur: { approved: number; rejected: number; not_sure: number; unreviewed: number },
  firstReview: boolean
) {
  let { approved, rejected, not_sure, unreviewed } = cur;
  if (firstReview) unreviewed = Math.max(0, unreviewed - 1);
  if (prevType === 'approved') approved -= 1;
  else if (prevType === 'rejected') rejected -= 1;
  else if (prevType === 'not_sure') not_sure -= 1;
  if (nextType === 'approved') approved += 1;
  else if (nextType === 'rejected') rejected += 1;
  else if (nextType === 'not_sure') not_sure += 1;
  return { approved, rejected, not_sure, unreviewed };
}

const glowKeyframes = keyframes`
  0%, 100% { box-shadow: 0 0 20px 4px rgba(234, 179, 8, 0.6), 0 0 40px 8px rgba(34, 197, 94, 0.3); }
  50% { box-shadow: 0 0 32px 8px rgba(234, 179, 8, 0.8), 0 0 60px 12px rgba(34, 197, 94, 0.5); }
`;

export const MediaReviewPage = () => {
  const { countryCode } = useParams<{ countryCode: string }>();
  const [searchParams] = useSearchParams();
  const urlSpeciesId = useMemo(() => {
    const n = Number(searchParams.get('species'));
    return Number.isInteger(n) && n > 0 ? n : null;
  }, [searchParams]);
  const [speciesWithMedia, setSpeciesWithMedia] = useState<SpeciesWithMedia[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasNextPage, setHasNextPage] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedMedia, setSelectedMedia] = useState<MediaItem | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [modalReviewSubmitting, setModalReviewSubmitting] = useState(false);
  const [machineOverrideNotice, setMachineOverrideNotice] = useState(false);
  const modalQueue = useMemo(() => speciesWithMedia.flatMap((g) => g.media), [speciesWithMedia]);
  const handleReviewRef = useRef<(mediaId: number, reviewType: 'approved' | 'rejected' | 'not_sure') => Promise<void>>(
    async () => {}
  );
  const [reviewedItems, setReviewedItems] = useState<Map<number, 'approved' | 'rejected' | 'not_sure'>>(new Map());
  const [selectedCountry, setSelectedCountry] = useState<string>(countryCode ?? '');
  const [speciesStats, setSpeciesStats] = useState<SpeciesReviewStatsResponse | null>(null);
  const [speciesStatsLoading, setSpeciesStatsLoading] = useState(true);
  const [selectedMediaType, setSelectedMediaType] = useState<'image' | 'video' | 'audio'>('image');
  const [showConfetti, setShowConfetti] = useState(false);
  const [celebrationSpeciesName, setCelebrationSpeciesName] = useState<string | null>(null);
  const [speciesList, setSpeciesList] = useState<Species[]>([]);
  const [speciesListLoading, setSpeciesListLoading] = useState(false);
  const [selectedSpecies, setSelectedSpecies] = useState<Species | null>(null);
  const [reviewLevel, setReviewLevel] = useState<ReviewLevel>('fast');
  const [tenApprovedSpeciesName, setTenApprovedSpeciesName] = useState<string | null>(null);
  const reviewStatsRef = useRef<HTMLDivElement | null>(null);
  const shouldScrollToNextRef = useRef(false);
  const SCROLL_OFFSET_TOP = 80;

  const STORAGE_KEY = 'media-review-instructions-collapsed';
  const [instructionsCollapsed, setInstructionsCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });
  const setInstructionsCollapsedWithStorage = useCallback((value: boolean) => {
    setInstructionsCollapsed(value);
    try {
      localStorage.setItem(STORAGE_KEY, String(value));
    } catch {
      /* ignore */
    }
  }, []);

  const [urlSpeciesReady, setUrlSpeciesReady] = useState(!urlSpeciesId);
  const skipNextCountrySpeciesClear = useRef(true);

  // Preselect country from URL when param is set or changes (e.g. navigation to /media-review/NL)
  useEffect(() => {
    if (countryCode) {
      const next = countryCode.toUpperCase();
      setSelectedCountry((prev) => (prev === next ? prev : next));
    }
  }, [countryCode]);

  // Clear species filter when country changes (but not on the initial render / URL preselect)
  useEffect(() => {
    if (skipNextCountrySpeciesClear.current) {
      skipNextCountrySpeciesClear.current = false;
      return;
    }
    setSelectedSpecies(null);
  }, [selectedCountry]);

  const { countries } = UseCountries();
  const { player, speciesLanguage } = useContext(AppContext);
  const intl = useIntl();
  const languageParam = speciesLanguage === 'nl' ? 'nl' : speciesLanguage === 'la' ? 'la' : (speciesLanguage ?? 'en');

  // Preselect species from ?species= (e.g. from a species page)
  useEffect(() => {
    if (!urlSpeciesId) {
      setUrlSpeciesReady(true);
      return;
    }
    let cancelled = false;
    setUrlSpeciesReady(false);
    fetchSpeciesDetail(urlSpeciesId, languageParam)
      .then((species) => {
        if (!cancelled) setSelectedSpecies(species);
      })
      .catch(() => {
        if (!cancelled) setSelectedSpecies(null);
      })
      .finally(() => {
        if (!cancelled) setUrlSpeciesReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [urlSpeciesId, languageParam]);

  // Load species for selected country (for filter dropdown)
  useEffect(() => {
    if (!selectedCountry) {
      setSpeciesList([]);
      return;
    }
    let cancelled = false;
    setSpeciesListLoading(true);
    fetch(`/api/species/?countryspecies__country=${selectedCountry}&language=${languageParam}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        const arr = Array.isArray(data) ? data : data?.results ?? data?.data ?? [];
        if (!cancelled) setSpeciesList(arr);
      })
      .catch(() => {
        if (!cancelled) setSpeciesList([]);
      })
      .finally(() => {
        if (!cancelled) setSpeciesListLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedCountry, languageParam]);

  const mediaTypeCollection = useMemo(
    () =>
      createListCollection({
        items: [
          { label: intl.formatMessage({ id: 'media type images', defaultMessage: 'Images' }), value: 'image' },
          { label: intl.formatMessage({ id: 'media type videos', defaultMessage: 'Videos' }), value: 'video' },
          { label: intl.formatMessage({ id: 'media type audio', defaultMessage: 'Audio' }), value: 'audio' },
        ],
      }),
    [intl]
  );

  const levelCollection = useMemo(
    () =>
      createListCollection({
        items: [
          { label: intl.formatMessage({ id: 'review level fast', defaultMessage: 'Fast' }), value: 'fast' },
          { label: intl.formatMessage({ id: 'review level full', defaultMessage: 'Full' }), value: 'full' },
          { label: intl.formatMessage({ id: 'review level thorough', defaultMessage: 'Thorough' }), value: 'thorough' },
        ],
      }),
    [intl]
  );

  const loadSpecies = useCallback(
    async (
      page: number = 1,
      reset: boolean = false,
      countryCode?: string,
      mediaType: 'image' | 'video' | 'audio' = 'image',
      speciesId?: number,
      level: ReviewLevel = 'fast'
    ) => {
      try {
        if (reset) {
          setLoading(true);
          setSpeciesWithMedia([]);
        } else {
          setLoadingMore(true);
        }

        const data = await mediaService.getMediaReviewSpecies(mediaType, page, countryCode, languageParam, speciesId, level);

        if (reset) {
          setSpeciesWithMedia(data.results);
        } else {
          setSpeciesWithMedia((prev) => [...prev, ...data.results]);
        }
        setHasNextPage(data.next !== null);
        setCurrentPage(page);
      } catch (error) {
        console.error('Error loading media:', error);
        toaster.create({
          title: intl.formatMessage({ id: 'error loading media', defaultMessage: 'Error loading media' }),
          colorPalette: 'error',
          duration: 4000,
        });
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [intl, languageParam]
  );

  useEffect(() => {
    if (!urlSpeciesReady) return;
    loadSpecies(1, true, selectedCountry || undefined, selectedMediaType, selectedSpecies?.id, reviewLevel);
  }, [urlSpeciesReady, selectedCountry, selectedMediaType, selectedSpecies?.id, reviewLevel, languageParam, loadSpecies]);

  useEffect(() => {
    let cancelled = false;
    setSpeciesStatsLoading(true);
    mediaService
      .getSpeciesReviewStats(selectedCountry || undefined, selectedMediaType, languageParam)
      .then((data) => {
        if (!cancelled) setSpeciesStats(data);
      })
      .catch(() => {
        if (!cancelled) setSpeciesStats(null);
      })
      .finally(() => {
        if (!cancelled) setSpeciesStatsLoading(false);
      });
    return () => { cancelled = true; };
  }, [selectedCountry, selectedMediaType, languageParam]);

  // After removing a species (10 approved), scroll to review stats with offset below top menu
  useEffect(() => {
    if (!shouldScrollToNextRef.current) return;
    shouldScrollToNextRef.current = false;
    const el = reviewStatsRef.current;
    if (el) {
      requestAnimationFrame(() => {
        const top = el.getBoundingClientRect().top + window.scrollY - SCROLL_OFFSET_TOP;
        window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
      });
    }
  }, [speciesWithMedia]);

  const loadMore = useCallback(() => {
    if (!loadingMore && hasNextPage) {
      loadSpecies(currentPage + 1, false, selectedCountry || undefined, selectedMediaType, selectedSpecies?.id, reviewLevel);
    }
  }, [currentPage, loadingMore, hasNextPage, loadSpecies, selectedCountry, selectedMediaType, selectedSpecies?.id, reviewLevel]);

  // Infinite scroll handler
  useEffect(() => {
    const handleScroll = () => {
      // Don't load if already loading or no more pages
      if (loadingMore || !hasNextPage) {
        return;
      }

      // Check if we're near the bottom of the page
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const windowHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight;
      
      // Load more when within 800px of the bottom
      if (scrollTop + windowHeight >= documentHeight - 800) {
        loadMore();
      }
    };

    // Use throttling to avoid too many calls
    let ticking = false;
    const throttledHandleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', throttledHandleScroll, { passive: true });
    // Also check on initial load in case content is shorter than viewport
    handleScroll();
    
    return () => window.removeEventListener('scroll', throttledHandleScroll);
  }, [loadMore, loadingMore, hasNextPage]);

  const handleImageClick = (item: MediaItem) => {
    setMachineOverrideNotice(false);
    setSelectedMedia(item);
    setIsDialogOpen(true);
  };

  useEffect(() => {
    setMachineOverrideNotice(false);
  }, [selectedMedia?.id]);

  const handleReview = async (mediaId: number, reviewType: 'approved' | 'rejected' | 'not_sure') => {
    const canReview = !!player || !!authService.getAccessToken();
    if (!canReview) {
      toaster.create({
        title: intl.formatMessage({ id: 'login to review', defaultMessage: 'Please log in to review media.' }),
        colorPalette: 'warning',
        duration: 4000,
      });
      return;
    }

    const item =
      selectedMedia?.id === mediaId
        ? selectedMedia
        : speciesWithMedia.flatMap((s) => s.media).find((m) => m.id === mediaId);
    if (!item) return;
    const speciesId = item.species_id;
    const speciesName = item.species_name;

    const previous = (reviewedItems.get(mediaId) ?? item.review_type ?? null) as
      | 'approved'
      | 'rejected'
      | 'not_sure'
      | null;
    const isFirstReview = previous == null;
    const prevType = previous;
    const useFirstAssertion =
      item.type === 'image' && reviewType !== 'not_sure' && (reviewType === 'approved' || reviewType === 'rejected');

    const reviewingFromModal = isDialogOpen && selectedMedia?.id === mediaId;
    if (reviewingFromModal) setModalReviewSubmitting(true);

    // Mark as reviewed immediately for visual feedback
    setReviewedItems((prev) => new Map(prev).set(mediaId, reviewType));

    // Optimistic update of in-memory species counts and media review_type
    setSpeciesWithMedia((prev) =>
      prev.map((s) => {
        if (s.id !== speciesId) return s;
        const counts = deltaSpeciesReviewCounts(prevType, reviewType, s, isFirstReview);
        return {
          ...s,
          unreviewed: counts.unreviewed,
          approved: counts.approved,
          rejected: counts.rejected,
          not_sure: counts.not_sure,
          media: s.media.map((m) => {
            if (m.id !== mediaId) return m;
            let machine_human_agreement: 'agree' | 'disagree' | null | undefined;
            if (m.type === 'image' && (reviewType === 'approved' || reviewType === 'rejected')) {
              const mp = m.machine_prediction;
              if (mp) {
                machine_human_agreement =
                  mp.predicted_review_type === reviewType ? 'agree' : 'disagree';
              }
            }
            return {
              ...m,
              review_type: reviewType,
              ...(machine_human_agreement !== undefined
                ? { machine_human_agreement }
                : {}),
            };
          }),
        };
      })
    );

    try {
      const playerToken = authService.getAccessToken() ? undefined : player?.token;
      if (useFirstAssertion) {
        await mediaService.reviewMediaFirstAssertion(mediaId, playerToken, reviewType);
      } else {
        await mediaService.reviewMedia(mediaId, playerToken, reviewType);
      }

      const speciesStatForToast = speciesStats?.species?.find((s) => s.id === speciesId);
      const approvedAfter = speciesStatForToast
        ? deltaSpeciesReviewCounts(
            prevType,
            reviewType,
            {
              approved: speciesStatForToast.approved,
              rejected: speciesStatForToast.rejected,
              not_sure: speciesStatForToast.not_sure,
              unreviewed: speciesStatForToast.unreviewed,
            },
            isFirstReview
          ).approved
        : 0;

      const messages = {
        approved:
          reviewLevel === 'fast'
            ? intl.formatMessage(
                { id: 'media approved count', defaultMessage: 'Media approved {count}/10' },
                { count: approvedAfter },
              )
            : intl.formatMessage({ id: 'media approved', defaultMessage: 'Media approved.' }),
        rejected: intl.formatMessage({ id: 'media rejected', defaultMessage: 'Media rejected.' }),
        not_sure: intl.formatMessage({ id: 'media not sure', defaultMessage: 'Marked as not sure.' }),
      };
      toaster.create({
        title: messages[reviewType],
        colorPalette: 'success',
        duration: 2000,
      });

      if (item.type === 'image' && (reviewType === 'approved' || reviewType === 'rejected')) {
        const mp = item.machine_prediction;
        if (mp && mp.predicted_review_type !== reviewType) {
          setMachineOverrideNotice(true);
        } else {
          setMachineOverrideNotice(false);
        }
      }

      if (speciesStats && speciesId != null) {
        setSpeciesStats((prev) => {
          if (!prev) return prev;
          const species = prev.species.find((s) => s.id === speciesId);
          if (!species) return prev;
          const counts = deltaSpeciesReviewCounts(prevType, reviewType, species, isFirstReview);
          const { unreviewed, approved, rejected, not_sure } = counts;
          if (!isFirstReview) {
            return {
              ...prev,
              species: prev.species.map((s) =>
                s.id === speciesId ? { ...s, unreviewed, approved, rejected, not_sure } : s
              ),
            };
          }
          const isNowFullyReviewed = unreviewed === 0;
          const hadTenApprovedBefore = species.approved >= 10;
          const isNowReviewed = !isNowFullyReviewed && approved >= 10;
          const wasPartlyAndNowReviewed = species.unreviewed > 0 && species.approved < 10 && isNowReviewed;
          const summary = {
            ...prev.summary,
            fully_reviewed: prev.summary.fully_reviewed + (isNowFullyReviewed ? 1 : 0),
            reviewed: (prev.summary.reviewed ?? 0) + (wasPartlyAndNowReviewed ? 1 : 0) - (isNowFullyReviewed && hadTenApprovedBefore ? 1 : 0),
            partly_reviewed: Math.max(
              0,
              prev.summary.partly_reviewed
                - (isNowFullyReviewed && !hadTenApprovedBefore ? 1 : 0)
                - (wasPartlyAndNowReviewed ? 1 : 0),
            ),
          };
          return {
            ...prev,
            species: prev.species.map((s) =>
              s.id === speciesId ? { ...s, unreviewed, approved, rejected, not_sure } : s
            ),
            summary,
          };
        });
      }

      const speciesStat = speciesStats?.species?.find((s) => s.id === speciesId);
      const unreviewedAfter = speciesStat
        ? deltaSpeciesReviewCounts(prevType, reviewType, speciesStat, isFirstReview).unreviewed
        : null;
      const isSpeciesFullyReviewed =
        isFirstReview && speciesId != null && speciesName && unreviewedAfter === 0;

      if (isSpeciesFullyReviewed) {
        setShowConfetti(true);
        setCelebrationSpeciesName(speciesName);
        setTimeout(() => setShowConfetti(false), 6000);
        setTimeout(() => setCelebrationSpeciesName(null), 12000);
      }

      if (
        isFirstReview &&
        reviewLevel === 'fast' &&
        reviewType === 'approved' &&
        speciesId != null &&
        speciesName &&
        approvedAfter >= 10
      ) {
        setTenApprovedSpeciesName(speciesName);
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 6000);
        setTimeout(() => setTenApprovedSpeciesName(null), 12000);
        shouldScrollToNextRef.current = true;
        setSpeciesWithMedia((prev) => prev.filter((s) => s.id !== speciesId));
        if (selectedMedia?.id === mediaId) {
          setIsDialogOpen(false);
          setSelectedMedia(null);
        }
      } else if (selectedMedia?.id === mediaId) {
        if (useFirstAssertion) {
          const idx = modalQueue.findIndex((m) => m.id === mediaId);
          const next = idx >= 0 ? modalQueue[idx + 1] : undefined;
          if (next) setSelectedMedia(next);
          else {
            setIsDialogOpen(false);
            setSelectedMedia(null);
          }
        } else {
          setIsDialogOpen(false);
          setSelectedMedia(null);
        }
      }
    } catch (error) {
      console.error('Error reviewing media:', error);
      setReviewedItems((prev) => {
        const newMap = new Map(prev);
        newMap.delete(mediaId);
        return newMap;
      });
      toaster.create({
        title: intl.formatMessage({ id: 'error reviewing media', defaultMessage: 'Error reviewing media' }),
        colorPalette: 'error',
        duration: 4000,
      });
    } finally {
      if (reviewingFromModal) setModalReviewSubmitting(false);
    }
  };

  handleReviewRef.current = handleReview;

  useEffect(() => {
    if (!isDialogOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (modalReviewSubmitting) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        setIsDialogOpen(false);
        setSelectedMedia(null);
        return;
      }

      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        const q = modalQueue;
        const cur = selectedMedia;
        if (!cur) return;
        const idx = q.findIndex((m) => m.id === cur.id);
        if (idx < 0) return;
        const delta = e.key === 'ArrowRight' ? 1 : -1;
        const next = q[idx + delta];
        if (next) setSelectedMedia(next);
        return;
      }

      if (selectedMedia?.type !== 'image') return;

      if (e.key === 'a' || e.key === 'A') {
        e.preventDefault();
        void handleReviewRef.current(selectedMedia.id, 'approved');
      } else if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        void handleReviewRef.current(selectedMedia.id, 'rejected');
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isDialogOpen, modalReviewSubmitting, modalQueue, selectedMedia]);

  const handleOkay = async () => {
    if (!selectedMedia || modalReviewSubmitting) return;
    await handleReview(selectedMedia.id, 'approved');
  };

  const handleBad = async () => {
    if (!selectedMedia || modalReviewSubmitting) return;
    await handleReview(selectedMedia.id, 'rejected');
  };

  return (
    <Page>
      {showConfetti && (
        <Box
          position="fixed"
          inset={0}
          zIndex={9999}
          pointerEvents="none"
          aria-hidden
        >
          <Confetti
            width={window.innerWidth}
            height={window.innerHeight}
            run={showConfetti}
            recycle={false}
            numberOfPieces={400}
          />
        </Box>
      )}
      {celebrationSpeciesName && (
        <Portal>
          <Flex
            position="fixed"
            inset={0}
            zIndex={10000}
            align="center"
            justify="center"
            p={6}
            bg="blackAlpha.600"
            onClick={() => setCelebrationSpeciesName(null)}
            pointerEvents="auto"
            aria-live="polite"
          >
            <Box
              onClick={(e) => e.stopPropagation()}
              position="relative"
              bg="green.600"
              color="white"
              borderRadius="2xl"
              p={8}
              maxW="420px"
              textAlign="center"
              animation={`${glowKeyframes} 1.5s ease-in-out infinite`}
              borderWidth="4px"
              borderColor="yellow.300"
              borderStyle="solid"
            >
              <Icon as={FaTrophy} boxSize={16} mb={4} color="yellow.200" />
              <Heading size="xl" mb={2}>
                <FormattedMessage id="well done" defaultMessage="Well done!" />
              </Heading>
              <Text fontSize="xl" fontWeight="bold" mb={2}>
                {celebrationSpeciesName}
              </Text>
              <Text fontSize="lg" opacity={0.95}>
                <FormattedMessage id="species fully reviewed message" defaultMessage="is now fully reviewed!" />
              </Text>
              <Button
                mt={6}
                size="lg"
                colorPalette="yellow"
                variant="outline"
                borderWidth="2px"
                onClick={() => setCelebrationSpeciesName(null)}
              >
                <FormattedMessage id="dismiss" defaultMessage="Dismiss" />
              </Button>
            </Box>
          </Flex>
        </Portal>
      )}
      {tenApprovedSpeciesName && (
        <Portal>
          <Flex
            position="fixed"
            inset={0}
            zIndex={10000}
            align="center"
            justify="center"
            p={6}
            bg="blackAlpha.600"
            onClick={() => setTenApprovedSpeciesName(null)}
            pointerEvents="auto"
            aria-live="polite"
          >
            <Box
              onClick={(e) => e.stopPropagation()}
              position="relative"
              bg="blue.600"
              color="white"
              borderRadius="2xl"
              p={8}
              maxW="420px"
              textAlign="center"
              animation={`${glowKeyframes} 1.5s ease-in-out infinite`}
              borderWidth="4px"
              borderColor="blue.200"
              borderStyle="solid"
            >
              <Icon as={FaTrophy} boxSize={16} mb={4} color="blue.200" />
              <Heading size="xl" mb={2}>
                <FormattedMessage id="ten approved title" defaultMessage="10 approved!" />
              </Heading>
              <Text fontSize="xl" fontWeight="bold" mb={2}>
                {tenApprovedSpeciesName}
              </Text>
              <Text fontSize="lg" opacity={0.95}>
                <FormattedMessage id="ten approved message" defaultMessage="Species complete! Scroll for more." />
              </Text>
              <Button
                mt={6}
                size="lg"
                colorPalette="blue"
                variant="outline"
                borderWidth="2px"
                onClick={() => setTenApprovedSpeciesName(null)}
              >
                <FormattedMessage id="dismiss" defaultMessage="Dismiss" />
              </Button>
            </Box>
          </Flex>
        </Portal>
      )}
      <Page.Header>
        <Heading color={'gray.800'} size={'lg'} m={0}>
          <FormattedMessage id={'media review'} defaultMessage={'Media Review'} />
        </Heading>
      </Page.Header>
      <Page.Body maxW="full">
          <Box backgroundColor={'blue.100'} borderColor={'blue.700'} color={'blue.700'} border={'2px solid'} padding={4}>
            <Flex
              as="button"
              width="100%"
              textAlign="left"
              alignItems="center"
              gap={2}
              cursor="pointer"
              fontWeight="bold"
              _hover={{ opacity: 0.9 }}
              onClick={() => setInstructionsCollapsedWithStorage(!instructionsCollapsed)}
            >
              <Icon as={instructionsCollapsed ? FaChevronRight : FaChevronDown} fontSize="sm" />
              <FormattedMessage id={'media review instruction title'} defaultMessage={"Instructions"} />
            </Flex>
            {!instructionsCollapsed && (
              <>
                <Text fontWeight={'bold'} pt={2}>
                  <FormattedMessage id={'media review intro'} defaultMessage={"Great that you are here and thank you for helping out improving the Birdr app!"} />
                </Text>
                <Text pt={2}>
                  <FormattedMessage
                    id={'media review more'}
                    defaultMessage={"To collect over one million images of birds I used and automated script. I tried to make it really smart, so it will collect the right pictures. Unfortunately it is not smart enough :-(. There are pictures of low quality, that have multiple species, nests, feathers or even just something completely different. Appears we still need that 'human touch'! That's were you come in. Here's how you can help."} />
                </Text>

                <Text fontWeight={'bold'} pt={4}>
                  <FormattedMessage id={'media review instruction title'} defaultMessage={"Instructions"} />
                </Text>
                <ListRoot pt={2} as='ol' listStyle={'cirlce'} gap={2}>
                  <ListItem flexDirection={'row'} gap={2} display={'flex'} alignItems={'center'}>
                    <FaArrowAltCircleRight />
                    <FormattedMessage
                      id={'media review instructions 1'}
                      defaultMessage={"Select a country in top right corner"} />
                  </ListItem>
                  <ListItem flexDirection={'row'} gap={2} display={'flex'} alignItems={'center'}>
                    <FaArrowAltCircleRight />
                    <FormattedMessage
                      id={'media review instructions 2'}
                      defaultMessage={"Scroll trough the list"} />
                  </ListItem>
                  <ListItem flexDirection={'row'} gap={2} display={'flex'} alignItems={'center'}>
                    <FaArrowAltCircleRight />
                    <FormattedMessage
                      id={'media review instructions 3'}
                      defaultMessage={"For each picture, hover over. Optional: Click it if you want to see the full image."} />
                  </ListItem>
                  <ListItem flexDirection={'row'} gap={2} display={'flex'} alignItems={'center'}>
                    <FaArrowAltCircleRight />
                    <Box>
                      {selectedMediaType === 'image' ? (
                        <FormattedMessage
                          id={'media review instructions 4 image'}
                          defaultMessage={'Click {ok} to approve the image or {bad} to reject it (first assertion). Open a picture to use the large preview and keyboard shortcuts A / R.'}
                          values={{
                            ok: (
                              <Icon as={BsCheckCircle} boxSize={5} color="green.600" display="inline" verticalAlign="middle" mx={0.5} />
                            ),
                            bad: (
                              <Icon as={BsXCircle} boxSize={5} color="red.600" display="inline" verticalAlign="middle" mx={0.5} />
                            ),
                          }}
                        />
                      ) : (
                        <FormattedMessage
                          id={'media review instructions 4'}
                          defaultMessage={"Click {ok} if the picture is ok, {question} if you don't know or {bad} if it should be removed."}
                          values={{
                            ok: (
                              <Icon as={BsCheckCircle} boxSize={5} color="green.600" display="inline" verticalAlign="middle" mx={0.5} />
                            ),
                            question: (
                              <Icon as={FaQuestion} boxSize={5} color="orange.600" display="inline" verticalAlign="middle" mx={0.5} />
                            ),
                            bad: (
                              <Icon as={BsXCircle} boxSize={5} color="red.600" display="inline" verticalAlign="middle" mx={0.5} />
                            ),
                          }}
                        />
                      )}
                    </Box>
                  </ListItem>
                </ListRoot>
              </>
            )}
          </Box>
          <Flex gap={3} alignItems="center" flexWrap="wrap" mt={4} mb={4}>
            <Box minW="160px">
              <Select.Root
                collection={mediaTypeCollection}
                value={[selectedMediaType]}
                onValueChange={(details: { value: string[] }) => {
                  const v = details.value[0];
                  if (v === 'image' || v === 'video' || v === 'audio') setSelectedMediaType(v);
                }}
              >
                <Select.HiddenSelect />
                <Select.Control>
                  <Select.Trigger>
                    <Select.ValueText placeholder={intl.formatMessage({ id: 'media type placeholder', defaultMessage: 'Media type...' })} />
                  </Select.Trigger>
                  <Select.IndicatorGroup>
                    <Select.Indicator />
                  </Select.IndicatorGroup>
                </Select.Control>
                <Portal>
                  <Select.Positioner>
                    <Select.Content>
                      {mediaTypeCollection.items.map((item: any) => (
                        <Select.Item key={item.value} item={item}>
                          <Select.ItemIndicator />
                          <Select.ItemText>{item.label}</Select.ItemText>
                        </Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Positioner>
                </Portal>
              </Select.Root>
            </Box>
            <Box minW="140px">
              <Select.Root
                collection={levelCollection}
                value={[reviewLevel]}
                onValueChange={(details: { value: string[] }) => {
                  const v = details.value[0];
                  if (v === 'fast' || v === 'full' || v === 'thorough') setReviewLevel(v);
                }}
              >
                <Select.HiddenSelect />
                <Select.Control>
                  <Select.Trigger>
                    <Select.ValueText placeholder={intl.formatMessage({ id: 'review level placeholder', defaultMessage: 'Level...' })} />
                  </Select.Trigger>
                  <Select.IndicatorGroup>
                    <Select.Indicator />
                  </Select.IndicatorGroup>
                </Select.Control>
                <Portal>
                  <Select.Positioner>
                    <Select.Content>
                      {levelCollection.items.map((item: any) => (
                        <Select.Item key={item.value} item={item}>
                          <Select.ItemIndicator />
                          <Select.ItemText>{item.label}</Select.ItemText>
                        </Select.Item>
                      ))}
                    </Select.Content>
                  </Select.Positioner>
                </Portal>
              </Select.Root>
            </Box>
            <Box minW="200px">
              <CountryCombobox
                countries={countries}
                value={selectedCountry ? (countries.find((c) => c.code === selectedCountry) ?? null) : null}
                onChange={(c) => setSelectedCountry(c?.code ?? '')}
                allowEmpty
              />
            </Box>
            {(selectedCountry || selectedSpecies) && (
              <Box minW="220px">
                <SpeciesCombobox
                  species={speciesList}
                  playerLanguage={languageParam}
                  value={selectedSpecies}
                  isClearable
                  onSelect={(s) => setSelectedSpecies(s)}
                  onClear={() => setSelectedSpecies(null)}
                  loading={speciesListLoading}
                  placeholder={<FormattedMessage id="filter by species" defaultMessage="Filter by species..." />}
                  emptyMessage={<FormattedMessage id="no species found" defaultMessage="No species found" />}
                />
              </Box>
            )}
          </Flex>
          {!speciesStatsLoading && speciesStats && (
            <Flex ref={reviewStatsRef} gap={6} mt={4} mb={4} flexWrap="wrap" fontWeight="bold">
              <Text color="green.700">
                <FormattedMessage id="species reviewed" defaultMessage="{count} reviewed" values={{ count: speciesStats.summary.reviewed ?? 0 }} />
              </Text>
              <Text color="green.500">
                <FormattedMessage id="species fully reviewed" defaultMessage="{count} fully reviewed" values={{ count: speciesStats.summary.fully_reviewed }} />
              </Text>
              <Text color="orange.600">
                <FormattedMessage id="species partly reviewed" defaultMessage="{count} partly reviewed" values={{ count: speciesStats.summary.partly_reviewed }} />
              </Text>
              <Text color="gray.600">
                <FormattedMessage id="species not reviewed" defaultMessage="{count} not reviewed" values={{ count: speciesStats.summary.not_reviewed }} />
              </Text>
            </Flex>
          )}
        {loading ? (
          <Text><FormattedMessage id="loading" defaultMessage="Loading..." /></Text>
        ) : (
          <Box>
            {speciesWithMedia.map((group) => (
                <Box key={group.id} mb={8}>
                  <Heading size="md" mb={2} color="gray.700">
                    {group.name}
                  </Heading>
                  <Text fontSize="sm" color="gray.600" mb={4}>
                    <FormattedMessage
                      id="species review stats line"
                      defaultMessage="{total} media · {unreviewed} unreviewed · {approved} approved · {rejected} rejected · {notSure} not sure"
                      values={{
                        total: group.total_media,
                        unreviewed: group.unreviewed,
                        approved: group.approved,
                        rejected: group.rejected,
                        notSure: group.not_sure,
                      }}
                    />
                  </Text>
                  <SimpleGrid columns={{ base: 2, md: 3, lg: 4 }} gap={4}>
                    {group.media.map((item) => {
                const reviewTypeRaw = reviewedItems.get(item.id) ?? item.review_type ?? undefined;
                const isReviewed = reviewTypeRaw !== undefined;
                const effectiveRt = effectiveReviewType(reviewTypeRaw);

                const overlayColor =
                  effectiveRt === 'approved'
                    ? 'rgba(34, 197, 94, 0.3)'
                    : effectiveRt === 'rejected'
                    ? 'rgba(239, 68, 68, 0.3)'
                    : 'transparent';

                return (
                  <Box
                    key={item.id}
                    borderRadius="8px"
                    overflow="hidden"
                    border="1px solid"
                    borderColor="gray.200"
                    position="relative"
                    opacity={isReviewed ? 0.5 : 1}
                    filter={isReviewed ? 'blur(2px)' : 'none'}
                    transition="opacity 0.3s, filter 0.3s, border-color 0.2s, transform 0.2s"
                    _hover={
                      item.type === 'image' || !isReviewed
                        ? {
                            borderColor: 'primary.500',
                            transform: 'scale(1.02)',
                            '& [data-buttons-overlay]': {
                              opacity: 1,
                            },
                          }
                        : {}
                    }
                  >
                    <Box
                      width="100%"
                      height="300px"
                      overflow="hidden"
                      bg="gray.100"
                      position="relative"
                    >
                      <Image
                        src={item.url}
                        alt={item.species_name}
                        width="100%"
                        height="100%"
                        objectFit="contain"
                        cursor={item.type === 'image' || !isReviewed ? 'pointer' : 'not-allowed'}
                        onClick={() => {
                          if (item.type === 'image') handleImageClick(item);
                          else if (!isReviewed) handleImageClick(item);
                        }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="150" height="150"%3E%3Crect fill="%23ddd" width="150" height="150"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999"%3EImage%3C/text%3E%3C/svg%3E';
                        }}
                      />
                      {/* Colored overlay for reviewed items */}
                      {isReviewed && (
                        <Box
                          position="absolute"
                          top={0}
                          left={0}
                          right={0}
                          bottom={0}
                          bg={overlayColor}
                          zIndex={2}
                          pointerEvents="none"
                        />
                      )}
                      {/* Buttons overlay - desktop only, visible on hover */}
                      {!isReviewed && (
                        <Flex
                          data-buttons-overlay
                          position="absolute"
                          bottom={0}
                          left={0}
                          right={0}
                          zIndex={3}
                          gap={2}
                          p={2}
                          justifyContent="center"
                          bg="rgba(0, 0, 0, 0.7)"
                          opacity={0}
                          transition="opacity 0.2s"
                          pointerEvents="auto"
                          display={{ base: 'none', md: 'flex' }}
                        >
                          <Button
                            type="button"
                            size="sm"
                            colorPalette="success"
                            onClick={() => handleReview(item.id, 'approved')}
                            minW="40px"
                            h="40px"
                            display="flex"
                            alignItems="center"
                            justifyContent="center"
                          >
                            <Icon as={BsCheckCircle} boxSize={5} />
                          </Button>
                          {item.type !== 'image' && (
                            <Button
                              type="button"
                              size="sm"
                              colorPalette="warning"
                              onClick={() => handleReview(item.id, 'not_sure')}
                              minW="40px"
                              h="40px"
                              display="flex"
                              alignItems="center"
                              justifyContent="center"
                            >
                              <Icon as={FaQuestion} boxSize={5} />
                            </Button>
                          )}
                          <Button
                            type="button"
                            size="sm"
                            colorPalette="error"
                            onClick={() => handleReview(item.id, 'rejected')}
                            minW="40px"
                            h="40px"
                            display="flex"
                            alignItems="center"
                            justifyContent="center"
                          >
                            <Icon as={BsXCircle} boxSize={5} />
                          </Button>
                        </Flex>
                      )}
                    </Box>
                    {/* Buttons below image - mobile only */}
                    {!isReviewed && (
                      <Flex
                        gap={2}
                        p={2}
                        justifyContent="center"
                        bg="gray.100"
                        borderTopWidth="1px"
                        borderColor="gray.200"
                        display={{ base: 'flex', md: 'none' }}
                      >
                        <Button
                          type="button"
                          size="sm"
                          colorPalette="success"
                          onClick={() => handleReview(item.id, 'approved')}
                          minW="40px"
                          h="40px"
                          display="flex"
                          alignItems="center"
                          justifyContent="center"
                        >
                          <Icon as={BsCheckCircle} boxSize={5} />
                        </Button>
                        {item.type !== 'image' && (
                          <Button
                            type="button"
                            size="sm"
                            colorPalette="warning"
                            onClick={() => handleReview(item.id, 'not_sure')}
                            minW="40px"
                            h="40px"
                            display="flex"
                            alignItems="center"
                            justifyContent="center"
                          >
                            <Icon as={FaQuestion} boxSize={5} />
                          </Button>
                        )}
                        <Button
                          type="button"
                          size="sm"
                          colorPalette="error"
                          onClick={() => handleReview(item.id, 'rejected')}
                          minW="40px"
                          h="40px"
                          display="flex"
                          alignItems="center"
                          justifyContent="center"
                        >
                          <Icon as={BsXCircle} boxSize={5} />
                        </Button>
                      </Flex>
                    )}
                  </Box>
                );
                    })}
                  </SimpleGrid>
                </Box>
            ))}

            {speciesWithMedia.length === 0 && !loading && (
              <Text textAlign="center" mt={8}>
                <FormattedMessage id={'no media found'} defaultMessage={'No media found'} />
              </Text>
            )}
            {loadingMore && (
              <Text textAlign="center" mt={4} mb={4}>
                <FormattedMessage id={'loading more'} defaultMessage={'Loading more...'} />
              </Text>
            )}
          </Box>
        )}

        {/* Dialog: first assertion preview (images); video/audio keep three-way review */}
        <DialogRoot
          open={isDialogOpen}
          onOpenChange={(e: { open: boolean }) => {
            if (!e.open) {
              setIsDialogOpen(false);
              setSelectedMedia(null);
            }
          }}
        >
          <DialogBackdrop />
          <DialogPositioner>
            <DialogContent maxW="92vw" maxH="92vh" overflow="auto">
              <DialogCloseTrigger />
              <DialogHeader>
                <FormattedMessage id={'first assertion review'} defaultMessage={'First assertion review'} />
              </DialogHeader>
              <DialogBody>
                {selectedMedia && (() => {
                  const modalRaw =
                    reviewedItems.get(selectedMedia.id) ?? selectedMedia.review_type ?? undefined;
                  const modalEffective = effectiveReviewType(modalRaw);
                  const statusBadge =
                    modalEffective === 'approved' ? (
                      <Badge colorPalette="green" size="lg">
                        <FormattedMessage id={'review badge approved'} defaultMessage={'Approved'} />
                      </Badge>
                    ) : modalEffective === 'rejected' ? (
                      <Badge colorPalette="red" size="lg">
                        <FormattedMessage id={'review badge rejected'} defaultMessage={'Rejected'} />
                      </Badge>
                    ) : (
                      <Badge colorPalette="gray" size="lg">
                        <FormattedMessage id={'review badge unreviewed'} defaultMessage={'Unreviewed'} />
                      </Badge>
                    );
                  return (
                  <Flex direction="column" gap={4} align="center">
                    <Flex align="center" gap={3} flexWrap="wrap" justify="center">
                      {statusBadge}
                      {modalReviewSubmitting && <Spinner size="sm" />}
                    </Flex>
                    <Box maxW="900px" w="100%" maxH="65vh" overflow="hidden" borderRadius="8px" bg="gray.50">
                      <Image
                        src={selectedMedia.url}
                        alt={selectedMedia.species_name}
                        style={{
                          width: '100%',
                          height: '100%',
                          maxHeight: '65vh',
                          objectFit: 'contain',
                        }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="800" height="600"%3E%3Crect fill="%23ddd" width="800" height="600"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999"%3EImage not available%3C/text%3E%3C/svg%3E';
                        }}
                      />
                    </Box>
                    <Box textAlign="center" w="100%" maxW="720px">
                      <Text fontSize="sm" color="gray.600">
                        ID: {selectedMedia.id}
                      </Text>
                      {selectedMedia.url && (
                        <Text fontSize="sm" color="gray.600" wordBreak="break-all">
                          URL: {selectedMedia.url}
                        </Text>
                      )}
                      {selectedMedia.link && (
                        <Text fontSize="sm" color="gray.600" wordBreak="break-all">
                          <FormattedMessage id={'link label'} defaultMessage={'Link'} />: {selectedMedia.link}
                        </Text>
                      )}
                      <Text fontWeight="bold" mt={2}>{selectedMedia.species_name}</Text>
                      {selectedMedia.contributor && (
                        <Text fontSize="sm" color="gray.600">
                          <FormattedMessage id={'contributor'} defaultMessage={'Contributor'} />: {selectedMedia.contributor}
                        </Text>
                      )}
                      {selectedMedia.source && (
                        <Text fontSize="sm" color="gray.600">
                          <FormattedMessage id={'source'} defaultMessage={'Source'} />: {selectedMedia.source}
                        </Text>
                      )}
                    </Box>
                    {selectedMedia.type === 'image' && (
                      <Box
                        w="100%"
                        maxW="720px"
                        p={4}
                        bg="purple.50"
                        borderRadius="md"
                        borderWidth="1px"
                        borderColor="purple.200"
                      >
                        <Text fontWeight="bold" color="purple.900" mb={2}>
                          <FormattedMessage
                            id="machine first assertion heading"
                            defaultMessage="Machine first assertion"
                          />
                        </Text>
                        {selectedMedia.machine_prediction ? (
                          <>
                            <Text fontSize="md" color="purple.950">
                              <FormattedMessage id="machine says" defaultMessage="Predicted" />:{' '}
                              {selectedMedia.machine_prediction.predicted_review_type === 'approved' ? (
                                <FormattedMessage id="machine approved" defaultMessage="Approved" />
                              ) : (
                                <FormattedMessage id="machine rejected" defaultMessage="Rejected" />
                              )}
                            </Text>
                            {selectedMedia.machine_prediction.confidence != null && (
                              <Text fontSize="sm" color="purple.800" mt={1}>
                                <FormattedMessage id="machine confidence" defaultMessage="Confidence" />:{' '}
                                {selectedMedia.machine_prediction.confidence.toFixed(2)}
                              </Text>
                            )}
                            <Text fontSize="sm" color="purple.800" mt={1}>
                              <FormattedMessage id="machine model" defaultMessage="Model" />:{' '}
                              {selectedMedia.machine_prediction.model_version}
                              {selectedMedia.machine_prediction.features_version
                                ? ` (${selectedMedia.machine_prediction.features_version})`
                                : ''}
                            </Text>
                          </>
                        ) : (
                          <Text fontSize="sm" color="gray.600">
                            <FormattedMessage
                              id="no machine prediction"
                              defaultMessage="No machine prediction yet (run infer_media_first_assertions)."
                            />
                          </Text>
                        )}
                        <Flex gap={2} flexWrap="wrap" mt={2} align="center">
                          {selectedMedia.machine_human_agreement === 'disagree' && (
                            <Badge colorPalette="orange" size="sm">
                              <FormattedMessage
                                id="machine disagrees with human"
                                defaultMessage="Differs from latest human review"
                              />
                            </Badge>
                          )}
                          {machineOverrideNotice && (
                            <Badge colorPalette="orange" size="sm">
                              <FormattedMessage
                                id="you overrode machine"
                                defaultMessage="Your choice differed from the machine"
                              />
                            </Badge>
                          )}
                        </Flex>
                      </Box>
                    )}
                    {selectedMedia.type === 'image' && (
                      <Text fontSize="xs" color="gray.500" textAlign="center" w="100%" maxW="720px">
                        <FormattedMessage
                          id={'first assertion shortcuts'}
                          defaultMessage={'Keyboard: A approve · R reject · Esc close · Arrow keys previous/next'}
                        />
                      </Text>
                    )}
                    <Flex gap={3} mt={2} flexWrap="wrap" justify="center">
                      <Button
                        type="button"
                        onClick={handleOkay}
                        colorPalette="success"
                        disabled={modalReviewSubmitting}
                      >
                        <FormattedMessage id={'approve'} defaultMessage={'Approve'} />
                      </Button>
                      <Button
                        type="button"
                        onClick={handleBad}
                        colorPalette="error"
                        disabled={modalReviewSubmitting}
                      >
                        <FormattedMessage id={'reject'} defaultMessage={'Reject'} />
                      </Button>
                      {selectedMedia.type !== 'image' && (
                        <Button
                          type="button"
                          onClick={() => void handleReview(selectedMedia.id, 'not_sure')}
                          colorPalette="warning"
                          disabled={modalReviewSubmitting}
                        >
                          <FormattedMessage id={'not sure'} defaultMessage={'Not Sure'} />
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          setIsDialogOpen(false);
                          setSelectedMedia(null);
                        }}
                      >
                        <FormattedMessage id={'close'} defaultMessage={'Close'} />
                      </Button>
                    </Flex>
                  </Flex>
                  );
                })()}
              </DialogBody>
            </DialogContent>
          </DialogPositioner>
        </DialogRoot>
      </Page.Body>
    </Page>
  );
};
