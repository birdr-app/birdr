from django.test import Client, TestCase

from jizz.models import UsageEvent


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
            HTTP_REFERER="https://motmot.club/site/faq/",
            HTTP_USER_AGENT="Mozilla/5.0",
            HTTP_HOST="motmot.club",
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
