# Scheduled jobs (server crontab on birdr.pro)

All times are server UTC; the National League commands work out each country's
capital-local time themselves and are idempotent, so a missed or doubled run is harmless.

```cron
# National League: close days/weeks, send 18:00 / 20:00 / Sunday / Monday pushes
*/15 * * * *  cd /path/to/jizz && ./venv/bin/python manage.py league_tick >> /var/log/birdr/league_tick.log 2>&1
# Pre-build today's + tomorrow's quiz (requests also build it lazily)
10 * * * *    cd /path/to/jizz && ./venv/bin/python manage.py league_generate >> /var/log/birdr/league_generate.log 2>&1
```

```cron
# Flock challenges: 1-day-left reminder, close ended ones, auto-renew, results push
5 * * * *     cd /path/to/jizz && ./venv/bin/python manage.py flock_tick >> /var/log/birdr/cron.log 2>&1
```

```cron
# Sitemaps: build sitemap.xml and the section files once an hour instead of per request
20 * * * *    cd /path/to/jizz && ./venv/bin/python manage.py build_sitemaps >> /var/log/birdr/build_sitemaps.log 2>&1
```

`build_sitemaps` writes to `SITEMAP_DIR` (default `jizz/sitemaps/` in the checkout). Django serves
the files from there as soon as they exist, and falls back to building per request when they
don't. nginx can serve `sitemap.xml` straight from the directory; see docs/GOOGLE_OAUTH_PRODUCTION.md.
Run it once by hand after deploying this, so the first request doesn't hit the slow path.

`league_generate` runs hourly so every timezone has tomorrow's quiz well before its midnight.

One-off launch invite (check counts first):

```bash
python manage.py league_invite --countries NL,LT,GB,ZA,US --dry-run
python manage.py league_invite --countries NL,LT,GB,ZA,US
```

Existing jobs: `daily_challenge_reminders`
(every 15–30 min), `daily_challenge_all_answered`, `daily_challenge_end_series`.
