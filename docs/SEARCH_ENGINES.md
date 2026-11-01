# Search engines other than Google

Google finds motmot.club through Search Console and the sitemap. The others need a
little setup once, and IndexNow to hear about new pages quickly.

## IndexNow (Bing, Yandex, Seznam, Naver, Yep)

IndexNow is one ping that all of these engines share. Bing also feeds DuckDuckGo,
Yahoo and Ecosia, so this covers most non-Google search.

- The key is `INDEXNOW_KEY` in settings. The matching file is
  `app/public/<key>.txt`; nginx serves it at `https://motmot.club/<key>.txt`, which
  only goes live after a frontend build and deploy. Check with
  `curl https://motmot.club/8e743f8dc9801973f11d858d59a58d74.txt` (must print the key,
  not HTML).
- Submit the sitemap URLs, in every locale:

  ```
  ./manage.py indexnow_submit --dry-run          # count only
  ./manage.py indexnow_submit                    # everything
  ./manage.py indexnow_submit --section pages    # just the main pages and updates
  ```

  Submit everything once, then a section when its pages change (for example `pages`
  after publishing an update). Don't resubmit unchanged URLs on every deploy.

## Webmaster tools

Each verifies with a meta tag, set through an environment variable on the server:

| Engine | Where | Variable |
|---|---|---|
| Bing (also DuckDuckGo, Yahoo, Ecosia) | bing.com/webmasters, or "Import from Google Search Console" | `BING_SITE_VERIFICATION` |
| Yandex | webmaster.yandex.com | `YANDEX_VERIFICATION` |

After verifying, submit `https://motmot.club/sitemap.xml` in each.
