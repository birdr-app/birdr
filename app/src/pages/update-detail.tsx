import { Box, Flex, Heading, Text } from '@chakra-ui/react';
import { format } from 'date-fns';
import { useContext, useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { CmsRichText } from '../components/cms-rich-text';
import { Loading } from '../components/loading';
import { UpdateThumbsUpButton } from '../components/updates/update-list-item';
import AppContext from '../core/app-context';
import { loadUpdateDetail, toggleUpdateThumbsUp, type UpdateDetail } from '../core/updates';
import { Page } from '../shared/components/layout';

export default function UpdateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { player, appLanguage } = useContext(AppContext);
  const [update, setUpdate] = useState<UpdateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    loadUpdateDetail(id, player?.token, appLanguage || 'en')
      .then((data) => {
        if (!data) {
          setError('Update not found');
        } else {
          setUpdate(data);
        }
      })
      .catch(() => setError('Failed to load update'))
      .finally(() => setLoading(false));
  }, [id, player?.token, appLanguage]);

  const handleToggle = async (next: boolean) => {
    if (!update || toggling) return;
    setToggling(true);
    const result = await toggleUpdateThumbsUp(update.id, next, player?.token);
    if (result) {
      setUpdate({
        ...update,
        thumbs_up_count: result.thumbs_up_count,
        user_has_thumbs_up: result.user_has_thumbs_up,
      });
    }
    setToggling(false);
  };

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="updates" defaultMessage="Updates" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Box mb={4}>
          <RouterLink to="/updates">
            <Text color="primary.600" fontSize="sm">
              ← <FormattedMessage id="back_to_updates" defaultMessage="Back to updates" />
            </Text>
          </RouterLink>
        </Box>
        {loading && <Loading />}
        {error && <Text color="red.500">{error}</Text>}
        {update && (
          <Box>
            <Heading size="lg" color="primary.800" mb={2}>
              {update.title}
            </Heading>
            <Flex justify="space-between" color="primary.600" fontSize="sm" mb={6}>
              <Text>{update.user.first_name || update.user.username}</Text>
              <Text fontStyle="italic">{format(new Date(update.created), 'PP')}</Text>
            </Flex>
            <CmsRichText content={update.body} />
            <UpdateThumbsUpButton
              updateId={update.id}
              active={update.user_has_thumbs_up}
              count={update.thumbs_up_count}
              disabled={toggling || !player}
              onToggle={handleToggle}
            />
            {!player && (
              <Text mt={2} fontSize="sm" color="gray.500">
                <FormattedMessage id="login_to_thumbs_up" defaultMessage="Join or log in to give a thumbs up." />
              </Text>
            )}
          </Box>
        )}
      </Page.Body>
    </Page>
  );
}
