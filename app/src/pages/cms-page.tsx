import { Box, Heading, Link, Spinner, Text } from '@chakra-ui/react';
import { ReactNode, useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { Link as RouterLink } from 'react-router-dom';
import { loadHelpPage, type PageDetail } from '../api/pages';
import { CmsRichText } from '../components/cms-rich-text';
import { Page } from '../shared/components/layout';

type CmsPageProps = {
  slug: string;
  headerTitle: ReactNode;
  showBackToHelp?: boolean;
};

export const CmsPage = ({ slug, headerTitle, showBackToHelp = false }: CmsPageProps) => {
  const [page, setPage] = useState<PageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    loadHelpPage(slug)
      .then(setPage)
      .catch((e: Error) => setError(e.message || 'Page not found'))
      .finally(() => setLoading(false));
  }, [slug]);

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          {headerTitle}
        </Heading>
      </Page.Header>
      <Page.Body>
        {showBackToHelp && (
          <Link asChild color="primary.500" fontSize="sm" display="inline-block">
            <RouterLink to="/help">
              ← <FormattedMessage id="back to help" defaultMessage="Back to overview" />
            </RouterLink>
          </Link>
        )}
        <Heading color="gray.800" size="lg" m={0}>
          {page?.title ?? slug}
        </Heading>
        <Box fontSize="16px" lineHeight="1.6">
          {loading && <Spinner />}
          {error && <Text color="red">{error}</Text>}
          {!loading && !error && page && <CmsRichText content={page.content} />}
          {!loading && !error && slug === 'about' ? (
            <Link
              href="https://github.com/birdr-app/birdr"
              target="_blank"
              rel="noopener noreferrer"
              color="primary.500"
              fontWeight="600"
              mt={4}
              display="inline-block"
            >
              https://github.com/birdr-app/birdr
            </Link>
          ) : null}
        </Box>
      </Page.Body>
    </Page>
  );
};
