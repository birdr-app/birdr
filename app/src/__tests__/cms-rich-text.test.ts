import { extractCmsHtml, rewriteLegacyGithubRepo } from '../components/cms-rich-text';

describe('rewriteLegacyGithubRepo', () => {
  it('points About GitHub links at birdr-app/birdr', () => {
    expect(rewriteLegacyGithubRepo('https://github.com/gannetson/birdr')).toBe(
      'https://github.com/birdr-app/birdr'
    );
    expect(
      extractCmsHtml('<p><a href="https://github.com/gannetson/birdr">GitHub</a></p>')
    ).toContain('https://github.com/birdr-app/birdr');
    expect(
      extractCmsHtml('<p><a href="https://github.com/gannetson/birdr">GitHub</a></p>')
    ).not.toContain('gannetson/birdr');
  });
});
