import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  Heading,
  HStack,
  Image,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { format, parseISO } from 'date-fns';
import { fetchMemberStats, type MemberStats } from '../api/member-stats';
import { countryCodeToFlag } from '../api/birdrJourney';

const {
  Root: DialogRoot,
  Backdrop: DialogBackdrop,
  Positioner: DialogPositioner,
  Content: DialogContent,
  Header: DialogHeader,
  Body: DialogBody,
  Footer: DialogFooter,
  CloseTrigger: DialogCloseTrigger,
} = Dialog;

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

function StatRow({ label, value }: { label: React.ReactNode; value: React.ReactNode }) {
  return (
    <HStack justify="space-between" align="flex-start" gap={4} py={1}>
      <Text color="gray.600" fontSize="sm">
        {label}
      </Text>
      <Text fontWeight="600" textAlign="right" fontSize="sm">
        {value}
      </Text>
    </HStack>
  );
}

function Section({ title, children }: { title: React.ReactNode; children: React.ReactNode }) {
  return (
    <Box borderTopWidth="1px" borderColor="gray.100" pt={3} mt={3}>
      <Heading size="sm" mb={2}>
        {title}
      </Heading>
      <VStack align="stretch" gap={1}>
        {children}
      </VStack>
    </Box>
  );
}

export function MemberStatsModal({ isOpen, onClose }: Props) {
  const intl = useIntl();
  const [stats, setStats] = useState<MemberStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchMemberStats()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load stats');
          setStats(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const memberSince = stats?.member_since
    ? format(parseISO(stats.member_since), 'd MMM yyyy')
    : '—';

  return (
    <DialogRoot open={isOpen} onOpenChange={(e: { open: boolean }) => !e.open && onClose()} size="md">
      <DialogBackdrop />
      <DialogPositioner>
        <DialogContent>
          <DialogHeader>
            <Heading size="md" m={0}>
              <FormattedMessage id="member_stats" defaultMessage="Member stats" />
            </Heading>
            <DialogCloseTrigger />
          </DialogHeader>
          <DialogBody>
            {loading && (
              <VStack py={8}>
                <Spinner colorPalette="primary" />
              </VStack>
            )}
            {error && (
              <Text color="red.600" fontSize="sm">
                {error}
              </Text>
            )}
            {!loading && !error && stats && (
              <VStack align="stretch" gap={0}>
                <StatRow
                  label={<FormattedMessage id="member_since" defaultMessage="Member since" />}
                  value={memberSince}
                />
                <StatRow
                  label={<FormattedMessage id="games_played" defaultMessage="Games played" />}
                  value={stats.games_played}
                />
                <StatRow
                  label={<FormattedMessage id="correct_answers" defaultMessage="Correct answers" />}
                  value={stats.correct_answers}
                />
                <StatRow
                  label={
                    <FormattedMessage id="species_identified" defaultMessage="Species identified" />
                  }
                  value={stats.species_identified}
                />
                {stats.best_score && (
                  <StatRow
                    label={<FormattedMessage id="best_quiz_score" defaultMessage="Best quiz score" />}
                    value={
                      <>
                        {stats.best_score.score.toLocaleString()}
                        {stats.best_score.country_name
                          ? ` · ${countryCodeToFlag(stats.best_score.country_code)} ${stats.best_score.country_name}`
                          : ''}
                      </>
                    }
                  />
                )}

                <Section
                  title={
                    <FormattedMessage id="country_challenge" defaultMessage="Country Challenge" />
                  }
                >
                  {stats.country_challenges.length === 0 ? (
                    <Text fontSize="sm" color="gray.500">
                      <FormattedMessage
                        id="member_stats_no_challenge"
                        defaultMessage="No Country Challenge started yet."
                      />
                    </Text>
                  ) : (
                    stats.country_challenges.map((row) => (
                      <HStack key={row.country_code} justify="space-between" align="center" gap={3}>
                        <HStack gap={2} minW={0}>
                          {row.level_icon_url ? (
                            <Image src={row.level_icon_url} alt="" boxSize="28px" borderRadius="md" />
                          ) : (
                            <Text fontSize="lg">{countryCodeToFlag(row.country_code)}</Text>
                          )}
                          <Box minW={0}>
                            <Text fontSize="sm" fontWeight="600" truncate>
                              {countryCodeToFlag(row.country_code)} {row.country_name}
                            </Text>
                            <Text fontSize="xs" color="gray.500">
                              {row.level_title}
                              {row.step_label ? ` · ${row.step_label}` : ''}
                              {row.step_total ? ` / ${row.step_total}` : ''}
                            </Text>
                          </Box>
                        </HStack>
                      </HStack>
                    ))
                  )}
                </Section>

                <Section title={<FormattedMessage id="survival" defaultMessage="Survival" />}>
                  {stats.survival.best_streak > 0 ? (
                    <>
                      <StatRow
                        label={
                          <FormattedMessage id="best_survival_streak" defaultMessage="Best streak" />
                        }
                        value={
                          <>
                            {stats.survival.best_streak}
                            {stats.survival.best_country_name
                              ? ` · ${countryCodeToFlag(stats.survival.best_country_code)} ${stats.survival.best_country_name}`
                              : ''}
                          </>
                        }
                      />
                      {stats.survival.records.slice(0, 5).map((row) => (
                        <StatRow
                          key={row.country_code}
                          label={`${countryCodeToFlag(row.country_code)} ${row.country_name}`}
                          value={intl.formatMessage(
                            { id: 'survival_streak_n', defaultMessage: '{count} in a row' },
                            { count: row.streak },
                          )}
                        />
                      ))}
                    </>
                  ) : (
                    <Text fontSize="sm" color="gray.500">
                      <FormattedMessage
                        id="member_stats_no_survival"
                        defaultMessage="No Survival runs yet."
                      />
                    </Text>
                  )}
                </Section>

                <Section
                  title={<FormattedMessage id="national_league" defaultMessage="National League" />}
                >
                  {stats.national_league.memberships === 0 ? (
                    <Text fontSize="sm" color="gray.500">
                      <FormattedMessage
                        id="member_stats_no_league"
                        defaultMessage="Not in a National League yet."
                      />
                    </Text>
                  ) : (
                    <>
                      <StatRow
                        label={
                          <FormattedMessage id="league_quizzes_played" defaultMessage="League quizzes" />
                        }
                        value={stats.national_league.quizzes_played}
                      />
                      <StatRow
                        label={<FormattedMessage id="daily_wins" defaultMessage="Daily wins" />}
                        value={stats.national_league.daily_wins}
                      />
                      <StatRow
                        label={
                          <FormattedMessage id="week_champions" defaultMessage="Week champions" />
                        }
                        value={stats.national_league.week_champions}
                      />
                      {stats.national_league.leagues.map((row) => (
                        <StatRow
                          key={row.country_code}
                          label={`${row.flag || countryCodeToFlag(row.country_code)} ${row.country_name}`}
                          value={
                            <>
                              {row.daily_wins > 0 && (
                                <FormattedMessage
                                  id="daily_wins_n"
                                  defaultMessage="{count} daily"
                                  values={{ count: row.daily_wins }}
                                />
                              )}
                              {row.daily_wins > 0 && row.week_champions > 0 ? ' · ' : null}
                              {row.week_champions > 0 && (
                                <FormattedMessage
                                  id="week_champions_n"
                                  defaultMessage="{count} week"
                                  values={{ count: row.week_champions }}
                                />
                              )}
                              {row.daily_wins === 0 && row.week_champions === 0 ? '—' : null}
                            </>
                          }
                        />
                      ))}
                    </>
                  )}
                </Section>

                <Section title={<FormattedMessage id="flocks" defaultMessage="Flocks" />}>
                  <StatRow
                    label={<FormattedMessage id="flocks_joined" defaultMessage="Flocks joined" />}
                    value={stats.flocks_joined}
                  />
                </Section>
              </VStack>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              <FormattedMessage id="close" defaultMessage="Close" />
            </Button>
          </DialogFooter>
        </DialogContent>
      </DialogPositioner>
    </DialogRoot>
  );
}
