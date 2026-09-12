# Google Login (Production and Local)

For Google OAuth to work you need: correct **nginx** (production) or **proxy** (local) so the callback URL and session cookie use the same host, **Django** settings, and **Google Cloud Console** redirect URIs.

## Local development (React app)

The React app uses **getSocialLoginBaseUrl()** so that in local dev the OAuth start URL is the **backend** (e.g. `http://127.0.0.1:8050`). That way the session cookie and Google's callback URL use the same host and "Session value state missing" is avoided.

1. When you click "Continue with Google" on `http://localhost:3000`, the app sends you to `http://127.0.0.1:8050/auth/login/google-oauth2/?redirect_uri=http://localhost:3000/login/google`. The backend sets the session cookie for `127.0.0.1:8050` and redirects to Google. Google then redirects back to `http://127.0.0.1:8050/auth/complete/google-oauth2/...`, the browser sends the cookie, and the backend completes the flow and redirects to `http://localhost:3000/login/google?access_token=...&refresh_token=...`.

2. In **Google Cloud Console** → Credentials → your OAuth 2.0 Client ID → **Authorized redirect URIs**, add:
   - **`http://127.0.0.1:8050/auth/complete/google-oauth2/`** (if your Django backend runs on port 8050; use your actual backend port).

3. Ensure your Django backend is running on the same host/port (e.g. `127.0.0.1:8050`). If you use a different port (e.g. 8000), set **`REACT_APP_API_URL=http://127.0.0.1:8000`** so the OAuth link and redirect URI match.

---

## Production

For Google OAuth to work in production you need: correct **nginx** proxy headers, **Django** settings (see `jizz/settings/production.py`), and **Google Cloud Console** redirect URIs.

## 0. Route API traffic to Django (fix 405 on POST /token/)

If the frontend and API use the same host (e.g. `birdr.pro`), nginx must send **API paths to Django** and only serve the SPA for other paths. Otherwise POST requests (e.g. `POST /token/` for login) hit the static file server and return **405 Not Allowed**.

Define a location that matches Django paths **before** your SPA catch-all:

```nginx
# Django (API, auth, admin, static prefix, media)
location ~ ^/(token|auth|api|admin|country|stat|media)/ {
    proxy_pass http://127.0.0.1:8050;   # or your Django backend
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# SPA (React app) – only for non-API, non-marketing paths (/play, /start, /login, …)
# Marketing `/` is an exact Django location (see below); do not send `/` to index.html.
location / {
    root /var/www/jizz/app/build;   # or your build output
    try_files $uri $uri/ /index.html;
}
```

Paths that must reach Django: `/token/`, `/token/refresh/`, `/auth/`, `/api/`, `/admin/`, `/country/`, `/stat/` (Django `STATIC_URL`), `/media/`.

**If `/auth/login/google-oauth2/` still returns the React app (index.html):** nginx may be using `location /` for that request. Use **prefix locations with `^~`** so these paths are taken first and never fall through to the SPA. Put these **before** your `location /` block:

```nginx
# Django – must appear BEFORE location /
location ^~ /auth/ {
    proxy_pass http://jizz;   # or http://127.0.0.1:8050
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /token/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /api/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /admin/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /country/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Join links (app + web fallback): use two regex locations so /join/.../web/ is SPA, the rest Django.
# If you currently have "location ^~ /join/ { proxy_pass http://jizz; ... }", replace it with:
location ~ ^/join/.+/web/?$ {
    root /var/www/jizz/app/build;   # or your SPA build output
    try_files $uri $uri/ /index.html;
}
location ~ ^/join/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Public share pages (Open Graph previews for WhatsApp / socials)
location ^~ /flocks/results/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /flocks/c/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /g/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# Public marketing HTML (Django) — /site/ is the marketing tree (landing, SEO pages, CMS).
# Exact / and old SEO prefixes stay on Django so they can 301 to /site/.
# Do not use `location ^~ /flocks/` here: /flocks/create and /flocks/:slug stay on the SPA.
location = / {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location = /flocks {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location = /flocks/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location = /robots.txt {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location = /sitemap.xml {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /sitemap- {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /how-it-works/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /bird-identification-quiz/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /learn-bird-identification/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /bird-quiz-by-country/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /birding-app/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /my-tricky-birds/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /countries/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /birds/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /compare/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /page/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /data/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location ^~ /site/ {
    proxy_pass http://jizz;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# SPA (React app) – /play and other app routes. Must come AFTER the Django locations above.
# The CRA build has index.html at the build root (not build/play/). Do not use
# `root …/build` inside `location /play` — that looks for build/play/index.html and 404s.
# Either omit a /play block and let this catch-all serve /play, or use try_files /index.html:
# location ^~ /play {
#     root /var/www/jizz/jizz/app/build;
#     try_files /index.html =404;
# }
location / {
    root /var/www/jizz/jizz/app/build;
    try_files $uri $uri/ /index.html;
}

```

Then keep your existing `location /` (SPA) and other blocks. Reload nginx: `sudo nginx -t && sudo systemctl reload nginx`.

### Compression, HTTP/2, and `/game` SPA fallback

Copy [`deploy/nginx-perf.conf`](../deploy/nginx-perf.conf) onto the VPS (gzip/brotli in `http { }`, `http2` on `listen 443 ssl`, and `location ^~ /game` before Django). Without the `/game` block, a refresh on `/game/play` can hit the marketing 404 instead of the CRA app.

Brotli needs the Ubuntu module: `sudo apt-get install -y libnginx-mod-brotli` (or `nginx-module-brotli`). Then `sudo nginx -t && sudo systemctl reload nginx`. Gunicorn and Daphne stay as they are.

## 1. Nginx

When proxying to Django (Gunicorn/Daphne), nginx must pass scheme and host so Django builds the right callback URL (HTTPS and correct host).

In the `location` block that proxies to your Django app, add:

```nginx
location / {
    proxy_pass http://127.0.0.1:8050;   # or your Django server
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    # If Django is served under a different host (e.g. api.example.com):
    # proxy_set_header X-Forwarded-Host $host;
}
```

- **`X-Forwarded-Proto $scheme`** — So Django sees the request as HTTPS and builds `https://...` URLs (required for the redirect_uri sent to Google).
- **`Host $host`** — So Django uses the same host the user sees (e.g. `jizz.be` or `birdr.pro`) when building the callback URL.

If your API is on a different host (e.g. `api.jizz.be`) and you want the callback URL to use that host, keep passing `Host` as the API host or use `X-Forwarded-Host` and `USE_X_FORWARDED_HOST = True` in Django (already set in production).

## 2. Django (production settings)

Already configured in `jizz/settings/production.py`:

- **`SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`** — Trusts nginx’s `X-Forwarded-Proto` so `request.is_secure()` is True and generated URLs use `https`.
- **`USE_X_FORWARDED_HOST = True`** — Uses `X-Forwarded-Host` (if set) for building absolute URLs.
- **`SOCIAL_AUTH_LOGIN_REDIRECT_URL`** — Frontend URL where users land after login (e.g. `https://jizz.be/login/google`).
- **`SOCIAL_AUTH_REDIRECT_IS_HTTPS = True`** — Tells social-auth to use HTTPS for redirect URIs.

Ensure `SOCIAL_AUTH_GOOGLE_OAUTH2_KEY` and `SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET` are set (e.g. via env) in production.

## 3. Google Cloud Console

The **Authorized redirect URI** that Google uses is your **backend** callback URL, not the frontend `/login/google` page.

1. Open [Google Cloud Console](https://console.cloud.google.com/) → your project → **APIs & Services** → **Credentials** → your OAuth 2.0 Client ID.
2. Under **Authorized redirect URIs** add the exact backend URL Django uses for the OAuth callback. That is:
   - `https://<your-api-host>/auth/complete/google-oauth2/`
   Examples:
   - `https://jizz.be/auth/complete/google-oauth2/`
   - `https://birdr.pro/auth/complete/google-oauth2/`
   Use the same scheme and host that nginx and Django use (the one in `ALLOWED_HOSTS` and that users hit when they start login).
3. Under **Authorized JavaScript origins** add your frontend origin(s), e.g.:
   - `https://jizz.be`
   - `https://birdr.pro`
4. Save.

If the redirect URI in the console does not match exactly (including trailing slash and `https`), Google will show “redirect_uri_mismatch” and login will fail.

**Fixing "Error 400: redirect_uri_mismatch"**

1. In [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → your OAuth 2.0 Client ID, open **Authorized redirect URIs**.
2. Add this **exact** URI (for birdr.pro): `https://birdr.pro/auth/complete/google-oauth2/` — **https**, host **birdr.pro**, path **/auth/complete/google-oauth2/** with a **trailing slash**. No typos.
3. Click **Save** (changes can take a minute to apply).
4. If it still fails, the URI Django sends may differ (e.g. wrong host or http). Check Django logs when you start Google login; the redirect_uri is often logged. The value Django sends must match the console exactly.

## 4. Frontend (env)

In production the app uses `REACT_APP_API_URL` so the “Continue with Google” link hits the backend. Set it to your backend root, e.g.:

- `REACT_APP_API_URL=https://jizz.be`  
  or  
- `REACT_APP_API_URL=https://birdr.pro`

(No trailing slash. The frontend will call `${REACT_APP_API_URL}/auth/login/google-oauth2/?redirect_uri=...`.)

## 5. Search Console / Bing (marketing site)

Accounts cannot be created in this repo. After deploy:

1. Optionally set `GOOGLE_SITE_VERIFICATION` and `BING_SITE_VERIFICATION` so the tokens appear in the marketing `<head>`.
2. In Google Search Console (and Bing Webmaster Tools), add `https://birdr.pro` and submit `https://birdr.pro/sitemap.xml`.
3. Confirm `robots.txt` is served by Django (`Disallow: /admin/`, `/api/`, `/token/` plus a Sitemap line).

Locally, Django on port 8050 serves `/`, intent pages, `/countries/`, `/birds/` and `/compare/`. The CRA app on port 3000 is the game (`/play`). `setupProxy.js` forwards those SEO prefixes to Django; it does not proxy `/` so the webpack dev server still works.

## Quick checklist

- [ ] Nginx: API paths (`/token/`, `/auth/`, `/api/`, etc.) go to Django; marketing `/`, `/countries/`, `/birds/`, `/compare/`, intent URLs, `robots.txt` and `sitemap.xml` go to Django; only then SPA `try_files` for `/play` and other app routes. (Fixes 405 on POST /token/.)
- [ ] Search Console / Bing: set `GOOGLE_SITE_VERIFICATION` / `BING_SITE_VERIFICATION` if you have tokens, then submit `https://birdr.pro/sitemap.xml`.
- [ ] Nginx: `proxy_set_header X-Forwarded-Proto $scheme;` and `proxy_set_header Host $host;` on the Django proxy.
- [ ] Django production: `SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_HOST`, `SOCIAL_AUTH_LOGIN_REDIRECT_URL`, `SOCIAL_AUTH_REDIRECT_IS_HTTPS` (and Google key/secret).
- [ ] Google Cloud: Authorized redirect URI = `https://<api-host>/auth/complete/google-oauth2/`; Authorized JavaScript origins = your frontend origin(s).
- [ ] Frontend: `REACT_APP_API_URL` set to backend root in production.
