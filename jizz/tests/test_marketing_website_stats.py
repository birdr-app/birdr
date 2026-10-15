from datetime import date, datetime

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from jizz.marketing_website_stats import (
    marketing_path_label,
    marketing_website_payload,
    normalize_marketing_path,
)
from jizz.models import Country, UsageEvent
from jizz.usage_analytics import is_crawler_user_agent


class MarketingWebsiteStatsTests(TestCase):
    def setUp(self):
        Country.objects.get_or_create(code="NL", defaults={"name": "Netherlands"})
        Country.objects.get_or_create(code="DE", defaults={"name": "Germany"})

    def _event(
        self,
        *,
        path,
        when,
        ip_address="203.0.113.10",
        country_code="NL",
        user_agent="Mozilla/5.0",
        referer_host="",
        utm_source="",
        utm_medium="",
        utm_campaign="",
    ):
        event = UsageEvent.objects.create(
            event_type="page_view",
            path=path,
            platform="web",
            ip_address=ip_address,
            country_code=country_code,
            user_agent=user_agent,
            referer_host=referer_host,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )
        aware = timezone.make_aware(datetime.combine(when, datetime.min.time().replace(hour=12)))
        UsageEvent.objects.filter(pk=event.pk).update(created_at=aware)
        return event

    def test_normalize_and_label_paths(self):
        self.assertEqual(normalize_marketing_path("/nl/site/community/"), "/site/community/")
        self.assertEqual(normalize_marketing_path("/site/faq"), "/site/faq/")
        self.assertEqual(marketing_path_label("/site/"), "Home")
        self.assertEqual(marketing_path_label("/site/community/"), "Community")
        self.assertIn("house-sparrow", marketing_path_label("/site/birds/house-sparrow/"))

    def test_payload_groups_visits_by_month_country_and_path(self):
        self._event(path="/site/", when=date(2026, 1, 5), ip_address="203.0.113.10", country_code="NL")
        self._event(path="/nl/site/", when=date(2026, 1, 20), ip_address="203.0.113.11", country_code="NL")
        self._event(
            path="/site/community/",
            when=date(2026, 1, 20),
            ip_address="198.51.100.8",
            country_code="DE",
        )
        self._event(path="/site/faq/", when=date(2026, 2, 3), ip_address="203.0.113.10", country_code="NL")
        self._event(path="/play", when=date(2026, 1, 5), ip_address="203.0.113.99", country_code="US")
        self._event(path="/site/my-edits/", when=date(2026, 1, 5), ip_address="203.0.113.12", country_code="NL")
        self._event(
            path="/site/",
            when=date(2026, 1, 6),
            ip_address="203.0.113.13",
            country_code="NL",
            user_agent="Mozilla/5.0 (compatible; Googlebot/2.1)",
        )

        payload = marketing_website_payload(date(2026, 1, 1), date(2026, 2, 28), granularity="month")
        by_period = {row["period"]: row for row in payload["series"]}
        self.assertEqual(payload["total_visits"], 4)
        self.assertEqual(payload["unique_visitors"], 3)
        self.assertEqual(payload["country_count"], 2)
        self.assertEqual(by_period["2026-01-01"]["visits"], 3)
        self.assertEqual(by_period["2026-01-01"]["visitors"], 3)
        self.assertEqual(by_period["2026-02-01"]["visits"], 1)
        self.assertEqual(payload["top_paths"][0]["path"], "/site/")
        self.assertEqual(payload["top_paths"][0]["visits"], 2)
        country_map = {row["country_code"]: row["visits"] for row in payload["by_country"]}
        self.assertEqual(country_map["NL"], 3)
        self.assertEqual(country_map["DE"], 1)
        self.assertEqual(payload["country_map"]["NL"], 3)
        self.assertNotIn("/play", [row["path"] for row in payload["top_paths"]])
        self.assertNotIn("/site/my-edits/", [row["path"] for row in payload["top_paths"]])

    def test_crawler_user_agent_helper(self):
        self.assertTrue(is_crawler_user_agent("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"))
        self.assertFalse(is_crawler_user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"))

    def test_payload_includes_referers_and_utms(self):
        self._event(
            path="/site/",
            when=date(2026, 3, 1),
            referer_host="t.co",
            utm_source="twitter",
            utm_medium="social",
            utm_campaign="spring",
        )
        self._event(
            path="/site/community/",
            when=date(2026, 3, 2),
            ip_address="203.0.113.20",
            referer_host="t.co",
            utm_source="twitter",
        )
        self._event(path="/site/faq/", when=date(2026, 3, 3), ip_address="203.0.113.30")

        payload = marketing_website_payload(date(2026, 3, 1), date(2026, 3, 31), granularity="month")
        self.assertEqual(payload["external_referer_visits"], 2)
        referers = {row["label"]: row["visits"] for row in payload["top_referers"]}
        self.assertEqual(referers["t.co"], 2)
        self.assertEqual(referers["Direct / unknown"], 1)
        self.assertEqual(payload["top_utm_sources"][0]["value"], "twitter")
        self.assertEqual(payload["top_utm_sources"][0]["visits"], 2)
        self.assertEqual(payload["top_utm_campaigns"][0]["value"], "spring")


class MarketingWebsiteViewsTests(TestCase):
    def test_page_and_api_are_public(self):
        res = Client().get(reverse("data-marketing-website"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Marketing website")
        self.assertContains(res, "marketing-visits-chart")
        self.assertContains(res, "Most visited pages")
        self.assertContains(res, "Where visitors came from")
        self.assertContains(res, reverse("data-marketing-website"), html=False)

        api = Client().get(
            reverse("data-marketing-website-api"),
            {"start": "2026-01-01", "end": "2026-01-31", "granularity": "month"},
        )
        self.assertEqual(api.status_code, 200)
        data = api.json()
        self.assertEqual(data["granularity"], "month")
        self.assertIn("series", data)
        self.assertIn("top_paths", data)
        self.assertIn("top_referers", data)
        self.assertIn("top_utm_sources", data)
        self.assertIn("by_country", data)
        self.assertIn("total_visits", data)

    def test_index_links_to_marketing_website(self):
        res = Client().get(reverse("data-index"))
        self.assertContains(res, reverse("data-marketing-website"))
        self.assertContains(res, "Marketing website")


class MarketingWebsiteTrackingTests(TestCase):
    def test_site_page_view_is_recorded(self):
        client = Client()
        response = client.get("/site/")
        self.assertEqual(response.status_code, 200)
        event = UsageEvent.objects.get()
        self.assertEqual(event.path, "/site/")
        self.assertEqual(event.event_type, "page_view")

    def test_site_page_view_captures_referer_and_utm(self):
        client = Client()
        response = client.get(
            "/site/?utm_source=newsletter&utm_medium=email&utm_campaign=march",
            HTTP_REFERER="https://news.ycombinator.com/item?id=1",
            HTTP_USER_AGENT="Mozilla/5.0",
        )
        self.assertEqual(response.status_code, 200)
        event = UsageEvent.objects.get()
        self.assertEqual(event.path, "/site/")
        self.assertEqual(event.referer_host, "news.ycombinator.com")
        self.assertEqual(event.utm_source, "newsletter")
        self.assertEqual(event.utm_medium, "email")
        self.assertEqual(event.utm_campaign, "march")
        self.assertEqual(event.metadata["traffic"]["referer"], "https://news.ycombinator.com/item?id=1")

    def test_same_origin_referer_is_treated_as_direct(self):
        client = Client()
        response = client.get(
            "/site/",
            HTTP_REFERER="https://birdr.pro/site/faq/",
            HTTP_USER_AGENT="Mozilla/5.0",
            HTTP_HOST="birdr.pro",
        )
        self.assertEqual(response.status_code, 200)
        event = UsageEvent.objects.get()
        self.assertEqual(event.referer_host, "")

    def test_crawler_site_view_is_not_recorded(self):
        client = Client()
        response = client.get(
            "/site/",
            HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UsageEvent.objects.count(), 0)
