"""HTML sanitizer for marketing text (comparisons, updates)."""

from django.test import TestCase

from jizz.marketing.html import sanitize_html


class SanitizeHtmlTests(TestCase):
    def test_strips_script_and_javascript_urls(self):
        html = sanitize_html(
            '<p>Hi</p><script>alert(1)</script><a href="javascript:alert(1)">x</a>'
            '<a href="/play">quiz</a>'
        )
        self.assertIn('<p>Hi</p>', html)
        self.assertNotIn('script', html)
        self.assertNotIn('javascript:', html)
        self.assertIn('href="/play"', html)

    def test_keeps_headings_lists_and_emphasis(self):
        html = sanitize_html(
            '<h2>Tips</h2><ul><li><strong>bold</strong></li></ul>'
            '<ol><li><em>one</em></li></ol><h3>More</h3>'
        )
        self.assertIn('<h2>Tips</h2>', html)
        self.assertIn('<ul>', html)
        self.assertIn('<ol>', html)
        self.assertIn('<strong>bold</strong>', html)
        self.assertIn('<em>one</em>', html)
        self.assertIn('<h3>More</h3>', html)
