import { QuillContentViewer } from './quill-content-viewer';

type QuillPayload = { delta?: unknown; html?: string };

const CMS_HTML_STYLES = `
  .help-page-content.help-page-html { font-size: 16px; line-height: 1.6; }
  .help-page-content.help-page-html p { margin-bottom: 12px; }
  .help-page-content.help-page-html h2 { font-size: 1.125rem; font-weight: bold; margin-top: 16px; margin-bottom: 8px; }
  .help-page-content.help-page-html h3 { font-size: 1rem; font-weight: bold; margin-top: 12px; margin-bottom: 8px; }
  .help-page-content.help-page-html ul { padding-left: 24px; margin-bottom: 12px; }
  .help-page-content.help-page-html a { color: var(--chakra-colors-primary-500, #3182ce); text-decoration: underline; }
  .help-page-content.help-page-html img {
    max-width: 100%; height: auto; border: 1px dashed #e2e8f0; border-radius: 8px;
    padding: 8px; background: #f7fafc; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    margin: 12px 0; display: block;
  }
`;

function isQuillContent(content: string): boolean {
  if (!content || typeof content !== 'string') return false;
  const t = content.trim();
  return t.startsWith('{') && (t.includes('"ops"') || t.includes('"delta"') || t.includes('"html"'));
}

const LEGACY_GITHUB_REPO = /https?:\/\/github\.com\/gannetson\/birdr/g;
const CURRENT_GITHUB_REPO = 'https://github.com/birdr-app/birdr';

export function rewriteLegacyGithubRepo(value: string): string {
  return value.replace(LEGACY_GITHUB_REPO, CURRENT_GITHUB_REPO);
}

/** Prefer stored HTML (same as mobile), otherwise leave Quill JSON for the delta viewer. */
export function extractCmsHtml(raw: string | object | null | undefined): string | null {
  if (raw == null) return null;
  if (typeof raw === 'object') {
    const obj = raw as QuillPayload;
    if (typeof obj.html === 'string' && obj.html.trim().length > 0) {
      return rewriteLegacyGithubRepo(obj.html);
    }
    return null;
  }
  const bodyStr = raw.trim();
  if (!bodyStr) return null;
  if (!bodyStr.startsWith('{')) return rewriteLegacyGithubRepo(bodyStr);
  try {
    const parsed = JSON.parse(bodyStr) as QuillPayload;
    if (typeof parsed?.html === 'string' && parsed.html.trim().length > 0) {
      return rewriteLegacyGithubRepo(parsed.html);
    }
  } catch {
    return rewriteLegacyGithubRepo(bodyStr);
  }
  return null;
}

export function CmsRichText({ content, className }: { content: string; className?: string }) {
  const html = extractCmsHtml(content);
  if (html) {
    return (
      <>
        <style>{CMS_HTML_STYLES}</style>
        <div
          className={`help-page-content help-page-html ${className ?? ''}`}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      </>
    );
  }
  if (isQuillContent(content)) {
    return <QuillContentViewer content={rewriteLegacyGithubRepo(content)} className={className} />;
  }
  return (
    <>
      <style>{CMS_HTML_STYLES}</style>
      <div
        className={`help-page-content help-page-html ${className ?? ''}`}
          dangerouslySetInnerHTML={{ __html: rewriteLegacyGithubRepo(content || '') }}
      />
    </>
  );
}
