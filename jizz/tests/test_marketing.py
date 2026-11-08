"""Public marketing pages, sitemap and robots."""

import re
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from compare.ai_service import HANDBOOK_MODEL, comparison_model_name, comparison_prompt_version
from compare.models import SpeciesComparison
from jizz.models import (
    Answer,
    BirdrJourney,
    Country,
    CountrySpecies,
    Game,
    Player,
    PlayerScore,
    Question,
    Species,
)
from media.models import Media, MediaReview

def _sitemap_lastmods(body: str) -> dict[str, str | None]:
    """<loc> -> <lastmod> (or None) for each <url> or <sitemap> entry."""
    entries = re.findall(r'<(?:url|sitemap)>(.*?)</(?:url|sitemap)>', body, re.S)
    result = {}
    for entry in entries:
        lastmod = re.search(r'<lastmod>(.*?)</lastmod>', entry)
        result[re.search(r'<loc>(.*?)</loc>', entry).group(1)] = lastmod.group(1) if lastmod else None
    return result


_SAMPLE_STORE_RATINGS = {
    'ios': {'score': 4.8, 'count': 12, 'score_label': '4.8', 'star_percent': 96},
    'android': {'score': 4.6, 'count': 9, 'score_label': '4.6', 'star_percent': 92},
}


class MarketingPagesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ratings_patcher = patch(
            'jizz.store_ratings.get_store_ratings',
            return_value=_SAMPLE_STORE_RATINGS,
        )
        self.ratings_patcher.start()
        self.addCleanup(self.ratings_patcher.stop)
        self.nl, _ = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        if self.nl.name != 'Netherlands':
            self.nl.name = 'Netherlands'
            self.nl.save(update_fields=['name'])
        Country.objects.get_or_create(code='world', defaults={'name': 'World'})
        Country.objects.get_or_create(code='NL-NH', defaults={'name': 'North Holland'})
        self.sparrow = Species.objects.create(
            name='Eurasian Sparrowhawk',
            name_latin='Accipiter nisus',
            code='eurspa',
        )
        self.goshawk = Species.objects.create(
            name='Northern Goshawk',
            name_latin='Accipiter gentilis',
            code='norgos',
        )
        Media.objects.create(
            species=self.sparrow,
            type='image',
            hide=False,
            url='https://upload.wikimedia.org/wikipedia/commons/a/a8/sparrowhawk.jpg',
        )
        Media.objects.create(
            species=self.goshawk,
            type='image',
            hide=False,
            url='https://upload.wikimedia.org/wikipedia/commons/b/b1/goshawk.jpg',
        )
        CountrySpecies.objects.get_or_create(country=self.nl, species=self.sparrow)
        CountrySpecies.objects.get_or_create(country=self.nl, species=self.goshawk)
        SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.sparrow,
            species_2=self.goshawk,
            summary='Sparrowhawks are smaller, with a squared tail; goshawks are bulkier.',
            detailed_comparison='Size, tail shape and flight style separate the two Accipiters.',
            identification_tips='Look at size against nearby birds, then tail corners.',
            ai_model=comparison_model_name(),
            ai_prompt_version=comparison_prompt_version(),
        )

    def test_legacy_home_redirects_to_site(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/site/')

    def test_legacy_redirects_keep_query_string(self):
        # Campaign links like the t-shirt QR code must keep their utm tags
        response = self.client.get('/?utm_source=tshirt')
        self.assertEqual(response['Location'], '/site/?utm_source=tshirt')
        response = self.client.get('/community/?utm_source=club')
        self.assertEqual(response['Location'], '/site/community/?utm_source=club')

    def test_landing_title_canonical_and_json_ld(self):
        response = self.client.get('/site/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Motmot – Free Bird Identification Quiz &amp; Training App', html)
        self.assertIn('Improve your birding skills.', html)
        self.assertIn('What is Motmot?', html)
        self.assertIn('sign in with Google so Motmot can create your account', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn('https://motmot.club/site/', html)
        self.assertIn('WebApplication', html)
        self.assertIn('MobileApplication', html)
        self.assertIn('"@type": "WebSite"', html)
        self.assertIn('"@type": "Organization"', html)
        self.assertIn('"url": "https://motmot.club/"', html)
        self.assertNotIn('FAQPage', html)
        self.assertIn('href="/site/community/"', html)
        self.assertIn('href="/site/faq/"', html)
        self.assertIn('href="/site/newsletter/"', html)
        self.assertIn('How you can help', html)
        self.assertIn('Read the FAQ', html)
        self.assertIn('Support Motmot', html)
        self.assertIn('https://buymeacoffee.com/loekd', html)
        # Hero and support box buttons both open the Buy Me a Coffee dialog
        self.assertEqual(html.count('class="btn btn-support"'), 2)
        self.assertIn('id="support-dialog"', html)
        self.assertIn('data-src="https://buymeacoffee.com/widget/page/loekd', html)
        self.assertNotIn('<iframe src="https://buymeacoffee.com', html)
        self.assertIn('id="support-birdr"', html)
        self.assertIn('There is no funding behind it right now', html)
        self.assertIn('Donating is one way', html)
        self.assertIn('Write about funding or a partnership', html)
        self.assertIn('Kudos to the developer!', html)
        self.assertIn('data-typewriter', html)
        self.assertIn('Baloo+2', html)
        self.assertIn('Figtree', html)
        self.assertIn('Bombay Natural History Society, India', html)
        self.assertIn('Kent Ornithological Society, United Kingdom', html)
        self.assertIn('BirdLife Finland (BirdLife Suomi), Finland', html)
        self.assertIn('Japan Bird Research Association, Japan', html)
        self.assertIn('info@motmot.club', html)
        self.assertIn('https://www.facebook.com/groups/birdrcommunity', html)
        self.assertIn('https://github.com/birdr-app/birdr/issues', html)
        self.assertIn('Get it on Google Play', html)
        self.assertIn('Or play a quiz in the browser', html)
        self.assertIn('href="/play"', html)
        self.assertIn('/images/motmot/screen-quiz-motmot.webp', html)
        self.assertIn('/images/motmot/tody-hello.webp', html)
        self.assertIn('What you can play', html)
        self.assertIn('Normal quizzes', html)
        self.assertIn('full control', html)
        self.assertIn('Country Challenge', html)
        self.assertIn('end is really tough', html)
        self.assertIn('Survival', html)
        self.assertIn('One wrong answer', html)
        self.assertIn('href="/survival"', html)
        self.assertIn('href="/site/survival/"', html)
        self.assertIn('Country records', html)
        self.assertIn('National League', html)
        self.assertIn('daily quiz', html)
        self.assertIn('href="/league"', html)
        self.assertIn('href="/site/national-league/"', html)
        self.assertIn('Countries with players', html)
        self.assertIn('Flocks', html)
        self.assertIn('entire week', html)
        self.assertIn('My Tricky Birds', html)
        self.assertIn('Difficult species', html)
        self.assertIn('Multiplayer', html)
        self.assertIn('two or more players', html)
        self.assertIn('Shared games', html)
        self.assertIn('Everyone has 3 days', html)
        self.assertIn('High scores', html)
        self.assertIn('href="/scores/"', html)
        self.assertIn('href="/checklist"', html)
        self.assertIn('Suggest a game type', html)
        self.assertIn('id="suggest-game"', html)
        self.assertIn('name="anchor"', html)
        self.assertIn('value="suggest-game"', html)
        self.assertIn('Send idea', html)

    def test_header_uses_tody_icon_wordmark_and_favicon(self):
        html = self.client.get('/site/').content.decode()
        self.assertIn('favicon-32x32.png', html)
        self.assertIn('class="brand-icon" src="/images/motmot/tody-icon-128.png"', html)
        self.assertIn('class="brand-wordmark" src="/images/motmot/wordmark-ink.svg"', html)
        self.assertIn('--brand: #A85B1B', html)
        self.assertIn('--correct: #1C7A4C', html)
        self.assertNotIn('#f7f1e6', html)
        icon = self.client.get('/images/motmot/tody-icon-128.png')
        self.assertEqual(icon.status_code, 200)
        self.assertIn('image/png', icon['Content-Type'])
        favicon = self.client.get('/favicon-32x32.png')
        self.assertEqual(favicon.status_code, 200)
        # Tody with binoculars in the menu bar
        self.assertIn('class="brand-icon" src="/images/motmot/tody-header-binoculars.webp"', html)
        self.assertEqual(self.client.get('/images/motmot/tody-header-binoculars.webp').status_code, 200)
        # Google search only shows favicons of at least 48x48
        self.assertIn('sizes="192x192" href="/android-chrome-192x192.png"', html)
        self.assertEqual(self.client.get('/android-chrome-192x192.png').status_code, 200)
        self.assertEqual(self.client.get('/android-chrome-512x512.png').status_code, 200)

    def test_motmot_brand_images_are_served(self):
        response = self.client.get('/images/motmot/tody-hello.webp')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/webp')
        wordmark = self.client.get('/images/motmot/wordmark-ink.svg')
        self.assertEqual(wordmark.status_code, 200)
        self.assertNotEqual(self.client.get('/images/motmot/../../package.json').status_code, 200)
        self.assertNotEqual(self.client.get('/images/motmot/tody-hello.txt').status_code, 200)

    def test_intent_and_mode_pages_show_tody(self):
        self.assertIn('/images/motmot/tody-flock.webp', self.client.get('/site/flocks/').content.decode())
        self.assertIn('/images/motmot/tody-champion.webp', self.client.get('/site/national-league/').content.decode())
        self.assertIn('/images/motmot/tody-stressed.webp', self.client.get('/site/survival/').content.decode())

    def test_login_script_defines_token_helper(self):
        html = self.client.get('/site/').content.decode()
        self.assertIn('function token() {', html)
        self.assertIn('token: token,', html)

    def test_home_screenshots_are_served_and_alt_text_translated(self):
        html = self.client.get('/nl/site/').content.decode()
        self.assertIn('/images/motmot/screen-league.webp', html)
        self.assertIn('Nederlandse league: de quiz van vandaag', html)
        response = self.client.get('/images/motmot/screen-quiz-motmot.webp')
        self.assertEqual(response.status_code, 200)

    def test_stylish_birdr_images_are_served(self):
        response = self.client.get('/images/stylish/birdr-waiting.png')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('image/'))

    def test_nav_shows_login_or_username(self):
        html = self.client.get('/site/').content.decode()
        self.assertIn('id="nav-login"', html)
        self.assertIn('Log in', html)
        self.assertIn('/login?next=', html)
        self.assertIn('id="login-dialog"', html)
        self.assertIn('birdrAuth', html)
        self.assertIn('id="nav-account"', html)
        self.assertRegex(html, r'id="nav-account"[^>]*hidden')
        self.assertNotIn('Ada Lovelace', html)

        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(
            'navada', password='x', first_name='Ada', last_name='Lovelace'
        )
        self.client.force_login(user)
        html = self.client.get('/site/').content.decode()
        self.assertIn('Ada Lovelace', html)
        self.assertIn('My Games', html)
        self.assertIn('My Checklist', html)
        self.assertIn('My tricky birds', html)
        self.assertIn('Settings', html)
        self.assertIn('My edits', html)
        self.assertIn('Logout', html)
        self.assertIn('href="/my-games"', html)
        self.assertIn('href="/checklist"', html)
        self.assertIn('href="/trouble-spots"', html)
        self.assertIn('href="/settings"', html)
        self.assertIn('href="/site/my-edits/"', html)
        self.assertRegex(html, r'id="nav-admin"[^>]*hidden')
        self.assertNotIn('id="nav-login"', html)

        staff = get_user_model().objects.create_user(
            'navstaff', password='x', first_name='Mod', is_staff=True
        )
        self.client.force_login(staff)
        staff_html = self.client.get('/site/').content.decode()
        self.assertIn('href="/admin"', staff_html)
        self.assertNotRegex(staff_html, r'id="nav-admin"[^>]*hidden')

    def test_intent_pages(self):
        paths = [
            '/site/how-it-works/',
            '/site/learn-bird-identification/',
            '/site/bird-quiz-by-country/',
            '/site/birding-app/',
            '/site/my-tricky-birds/',
            '/site/flocks/',
            '/site/community/',
            '/site/newsletter/',
            '/site/faq/',
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('rel="canonical"', html)
                self.assertIn(f'https://motmot.club{path}', html)
                self.assertIn('<title>', html)

        how = self.client.get('/site/how-it-works/').content.decode()
        # Play together: multiplayer and shared quizzes, with the lobby screenshot
        self.assertIn('id="play-together"', how)
        self.assertIn('/images/motmot/screen-lobby.webp', how)
        self.assertEqual(self.client.get('/images/motmot/screen-lobby.webp').status_code, 200)
        # The CTA already goes to /play, so no second browser link beside it
        self.assertNotIn('</a>\n    <a class="web-link" href="/play">', how)
        self.assertRegex(how, r'href="/site/how-it-works/"[^>]*aria-current="page"')
        self.assertNotRegex(how, r'href="/site/birds/"[^>]*aria-current="page"')
        self.assertIn('Beginner', how)
        self.assertIn('Novice', how)
        self.assertIn('Advanced', how)
        self.assertIn('>Pro<', how)
        self.assertIn('Expert', how)
        self.assertIn('familiar, distinctive species', how)
        self.assertIn('Type the name yourself', how)
        self.assertIn('class="card"', how)
        self.assertNotRegex(how, r'<p class="kicker">\d+</p>')
        self.assertIn('Species language', how)
        self.assertIn('Number of questions', how)
        self.assertIn('Taxonomic order / family', how)
        self.assertIn('Pictures, sounds or video', how)

        tricky = self.client.get('/site/my-tricky-birds/').content.decode()
        self.assertNotIn('Most missed species', tricky)
        self.assertNotIn('Confusing pairs', tricky)
        self.assertIn('/images/motmot/screen-tricky.webp', tricky)
        self.assertIn('/images/motmot/screen-tricky-pairs.webp', tricky)
        self.assertIn('/images/motmot/screen-tricky-comparison.webp', tricky)
        self.assertNotIn('/images/birdr-tricky-', tricky)
        self.assertIn('Your tricky birds', tricky)
        self.assertIn('Your tricky pairs', tricky)
        self.assertIn('Compare a pair', tricky)
        for path in (
            '/images/motmot/screen-tricky.webp',
            '/images/motmot/screen-tricky-pairs.webp',
            '/images/motmot/screen-tricky-comparison.webp',
        ):
            shot = self.client.get(path)
            self.assertEqual(shot.status_code, 200, path)
            self.assertEqual(shot['Content-Type'], 'image/webp')

        flocks = self.client.get('/site/flocks/').content.decode()
        self.assertIn('Flocks: quizzes for bird clubs', flocks)
        self.assertIn('/flocks/intro', flocks)

        by_country = self.client.get('/site/bird-quiz-by-country/').content.decode()
        self.assertIn('National League is the real competition', by_country)
        self.assertIn('href="/league"', by_country)
        self.assertIn('Open the National League', by_country)
        self.assertIn('class="country-pills"', by_country)
        self.assertIn('class="country-flag"', by_country)
        self.assertIn('Netherlands', by_country)

        community = self.client.get('/site/community/').content.decode()
        self.assertIn('How can I help?', community)
        self.assertIn('Facebook group', community)
        self.assertIn('the place to have discussions', community)
        self.assertIn('https://www.facebook.com/groups/birdrcommunity', community)
        self.assertIn('submit a ticket on GitHub', community)
        self.assertIn('https://github.com/birdr-app/birdr/issues', community)
        self.assertIn('Flag', community)
        self.assertIn('#review-photos', community)
        self.assertIn('/media-review/', community)
        self.assertIn('Write comparisons', community)
        self.assertIn('Write a better description', community)
        self.assertIn('href="/site/birds/"', community)
        self.assertRegex(community, r'href="/site/community/"[^>]*aria-current="page"')
        self.assertIn('Spread the word', community)
        self.assertIn('href="/site/newsletter/"', community)
        self.assertIn('See a newsletter example', community)
        self.assertIn('Leave a store review', community)
        self.assertIn('helps other birders find Motmot', community)
        self.assertIn('Review on the App Store', community)
        self.assertIn('Review on Google Play', community)
        self.assertIn('action=write-review', community)
        self.assertIn('class="store-score"', community)
        self.assertIn('>4.8<', community)
        self.assertIn('>4.6<', community)
        self.assertIn('12 ratings', community)
        self.assertIn('9 ratings', community)
        self.assertIn('Support Motmot', community)
        self.assertIn('https://buymeacoffee.com/loekd', community)
        self.assertIn('btn-support', community)
        self.assertIn('buy Motmot a coffee', community)
        self.assertIn('id="support-birdr"', community)
        self.assertIn('Donating is one way', community)
        self.assertIn('partnership', community)
        self.assertNotIn('Example newsletter item', community)
        self.assertNotIn('data-newsletter-copy', community)

        newsletter = self.client.get('/site/newsletter/').content.decode()
        self.assertIn('Add it to your bird club newsletter', newsletter)
        self.assertIn('Example newsletter item', newsletter)
        self.assertIn('data-newsletter-copy', newsletter)
        self.assertIn('newsletter-copy-body', newsletter)
        self.assertIn('A free bird ID quiz you can try yourself', newsletter)
        self.assertIn('Want to get sharper at bird identification between outings', newsletter)
        self.assertIn('quizzes for every level', newsletter)
        self.assertIn('free, open source, and has no ads', newsletter)
        self.assertIn('you practise the field marks yourself', newsletter)
        self.assertIn('get those warblers right', newsletter)
        self.assertIn('class="newsletter-shot"', newsletter)
        self.assertIn('More media', newsletter)
        self.assertIn('class="newsletter-more-grid"', newsletter)
        self.assertIn('They are not included when you press Copy', newsletter)
        self.assertIn('from easy to hard', newsletter)
        self.assertIn('App Store:', newsletter)
        self.assertIn('Google Play:', newsletter)
        self.assertIn('apps.apple.com/us/app/motmot-bird-id-quiz', newsletter)
        self.assertIn('play.google.com/store/apps/details?id=pro.birdr.app', newsletter)
        # Current screenshots, as PNG so they show when pasted into email or Word.
        shots = ['quiz', 'new-game', 'comparison', 'tricky-birds', 'tricky-pairs', 'country-challenge', 'league']
        public = Path(__file__).resolve().parents[2] / 'app' / 'public'
        for name in shots:
            self.assertIn(f'/images/newsletter/{name}.png', newsletter)
            self.assertTrue((public / 'images' / 'newsletter' / f'{name}.png').is_file(), name)
        club_section = newsletter[newsletter.index('id="club-newsletter"'):]
        self.assertNotIn('/images/birdr-', club_section.split('</section>\n  <script>')[0])
        copy_start = newsletter.index('id="newsletter-copy-body"')
        copy_end = newsletter.index('id="newsletter-more-heading"')
        copied = newsletter[copy_start:copy_end]
        for name in shots[:3]:
            self.assertIn(f'/images/newsletter/{name}.png', copied)
        for name in shots[3:]:
            self.assertNotIn(f'/images/newsletter/{name}.png', copied)
        self.assertRegex(newsletter, r'href="/site/community/"[^>]*aria-current="page"')
        self.assertIn('href="/site/newsletter/"', newsletter)
        for path in (
            '/images/birdr-new-game.png',
            '/images/birdr-photo-quiz.png',
            '/images/birdr-species-review.png',
            '/images/birdr-country-challenge.png',
        ):
            shot = self.client.get(path)
            self.assertEqual(shot.status_code, 200, path)
            self.assertEqual(shot['Content-Type'], 'image/png')

        faq = self.client.get('/site/faq/').content.decode()
        self.assertIn('FAQPage', faq)
        self.assertIn('Is Motmot free?', faq)
        self.assertIn('What are Flocks?', faq)

    def test_community_hides_store_scores_when_unavailable(self):
        with patch(
            'jizz.store_ratings.get_store_ratings',
            return_value={'ios': None, 'android': None},
        ):
            html = self.client.get('/site/community/').content.decode()
        self.assertIn('Leave a store review', html)
        self.assertIn('Review on the App Store', html)
        self.assertNotIn('class="store-score"', html)
        self.assertNotIn('class="store-score-row"', html)

    def test_legacy_marketing_paths_redirect(self):
        pairs = [
            ('/how-it-works/', '/site/how-it-works/'),
            ('/bird-identification-quiz/', '/play'),
            ('/site/bird-identification-quiz/', '/play'),
            ('/flocks/', '/site/flocks/'),
            ('/community/', '/site/community/'),
            ('/newsletter/', '/site/newsletter/'),
            ('/faq/', '/site/faq/'),
            ('/countries/netherlands/', '/site/countries/netherlands/'),
        ]
        for old, new in pairs:
            with self.subTest(old=old):
                response = self.client.get(old)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response['Location'], new)

    def test_unknown_url_is_404(self):
        response = self.client.get('/definitely-not-a-marketing-page/')
        self.assertEqual(response.status_code, 404)

    def test_country_page_and_skipped_rows(self):
        response = self.client.get('/site/countries/netherlands/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Netherlands', html)
        self.assertIn('Start a quiz', html)
        self.assertIn('Country Challenge', html)
        self.assertIn('National League', html)
        self.assertIn('/league/NL', html)
        self.assertIn('No one has played this week', html)
        self.assertIn('Play today’s National League quiz', html)
        self.assertIn('/media-review/NL', html)
        self.assertIn('Review Netherlands photos', html)
        self.assertIn('Spread the word', html)
        self.assertIn('/site/newsletter/', html)
        self.assertNotIn('Example newsletter item', html)
        self.assertIn('How people play in Netherlands', html)
        self.assertNotIn('High scores', html)
        self.assertEqual(self.client.get('/site/countries/world/').status_code, 404)
        self.assertEqual(self.client.get('/site/countries/north-holland/').status_code, 404)
        self.assertEqual(self.client.get('/site/countries/not-a-country/').status_code, 404)

    def test_species_index_search_and_sections(self):
        from jizz.models import TaxonomicFamily

        family = TaxonomicFamily.objects.create(
            name_latin='Accipitridae',
            name_en='Hawks, eagles and kites',
            name_nl='Haviken',
        )
        self.sparrow.taxonomic_family = family
        self.sparrow.save(update_fields=['taxonomic_family'])
        self.goshawk.taxonomic_family = family
        self.goshawk.save(update_fields=['taxonomic_family'])

        landing = self.client.get('/site/').content.decode()
        self.assertIn('href="/site/birds/"', landing)

        redirect = self.client.get('/birds/')
        self.assertEqual(redirect.status_code, 301)
        self.assertEqual(redirect['Location'], '/site/birds/')

        page = self.client.get('/site/birds/')
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn('Find a bird', html)
        self.assertIn('name="q"', html)
        self.assertIn('How to tell them apart', html)
        self.assertIn('Eurasian Sparrowhawk', html)
        self.assertIn('Northern Goshawk', html)
        self.assertIn('Browse by country', html)
        self.assertIn('Hawks, eagles and kites', html)

        search = self.client.get('/site/birds/', {'q': 'sparrow'}).content.decode()
        self.assertIn('Results for', search)
        self.assertIn(f'/site/birds/{self.sparrow.slug}/', search)

        short = self.client.get('/site/birds/', {'q': 's'}).content.decode()
        self.assertIn('at least two letters', short)
        self.assertNotIn('Results for', short)

        family_html = self.client.get('/site/birds/', {'family': 'Accipitridae'}).content.decode()
        self.assertIn('Hawks, eagles and kites', family_html)
        self.assertIn('Eurasian Sparrowhawk', family_html)
        self.assertIn('Northern Goshawk', family_html)

        game = Game.objects.create(
            country=self.nl,
            level='beginner',
            length=10,
            media='images',
            multiplayer=False,
        )
        question = Question.objects.create(
            game=game, species=self.goshawk, number=1, sequence=1,
        )
        for i in range(10):
            player = Player.objects.create(name=f'Index-miss-{i}', language='en')
            score = PlayerScore.objects.create(player=player, game=game, score=10)
            Answer.objects.create(
                player_score=score,
                question=question,
                answer=self.sparrow,
                correct=False,
            )
        cache.clear()
        missed = self.client.get('/site/birds/').content.decode()
        self.assertIn('Most missed species', missed)
        self.assertIn('Confusing pairs', missed)
        self.assertIn('/data/quiz-mistakes/species/', missed)

    def test_species_index_caches_expensive_queries(self):
        from jizz.marketing.pages import public_species_count, public_species_ids
        from jizz.marketing.species_index import featured_comparisons, public_families
        from jizz.marketing.views import _indexable_countries

        families = public_families()
        count = public_species_count()
        featured = featured_comparisons()
        countries = _indexable_countries()
        ids = public_species_ids()
        with self.assertNumQueries(0):
            self.assertEqual(public_families(), families)
            self.assertEqual(public_species_count(), count)
            self.assertEqual(featured_comparisons(), featured)
            self.assertEqual(_indexable_countries(), countries)
            self.assertEqual(public_species_ids(), ids)

    def test_country_page_stats_from_data_section(self):
        CountrySpecies.objects.filter(country=self.nl).update(status='native')
        game = Game.objects.create(
            country=self.nl,
            level='beginner',
            length=10,
            media='images',
            multiplayer=False,
        )
        player = Player.objects.create(name='Ada', language='en')
        PlayerScore.objects.create(player=player, game=game, score=4200)
        BirdrJourney.objects.create(player=player, country=self.nl, current_sequence=0)
        question = Question.objects.create(
            game=game,
            species=self.goshawk,
            number=1,
            sequence=1,
        )
        for i in range(3):
            p = Player.objects.create(name=f'Miss-{i}', language='en')
            score = PlayerScore.objects.create(player=p, game=game, score=10)
            Answer.objects.create(
                player_score=score,
                question=question,
                answer=self.sparrow,
                correct=False,
            )

        html = self.client.get('/site/countries/netherlands/').content.decode()
        self.assertIn('How people play in Netherlands', html)
        self.assertIn('Quizzes played', html)
        self.assertIn('High scores', html)
        self.assertIn('Ada', html)
        self.assertIn('4200', html)
        self.assertIn('/scores/?country=NL', html)
        self.assertIn('Country Challenge', html)
        self.assertIn('/data/country-challenge-leaderboard/?country=NL', html)
        self.assertIn('National League', html)
        self.assertIn('/league/NL', html)
        self.assertIn('Most missed birds', html)
        self.assertIn('Eurasian Sparrowhawk', html)
        self.assertIn('Confusing pairs', html)
        self.assertIn('vs', html)
        self.assertIn('/data/quiz-mistakes/species/?country=NL', html)
        self.assertIn('/data/quiz-mistakes/pairs/?country=NL', html)

    def test_country_page_national_league_standings(self):
        from django.contrib.auth.models import User
        from django.utils import timezone

        from jizz import league
        from jizz.models import Game, LeagueAttempt, LeagueDay, Player

        CountrySpecies.objects.filter(country=self.nl).update(status='native')
        if not self.nl.timezone:
            self.nl.timezone = 'Europe/Amsterdam'
            self.nl.save(update_fields=['timezone'])
        user = User.objects.create_user('league-ada', password='x', first_name='Ada')
        player = Player.objects.create(name='Ada League', language='en', user=user)
        today = league.league_local_now(self.nl).date()
        day = LeagueDay.objects.create(country=self.nl, date=today, length=10)
        game = Game.objects.create(
            country=self.nl,
            level='advanced',
            length=10,
            media='images',
            multiplayer=False,
            game_type=Game.GAME_TYPE_LEAGUE,
        )
        LeagueAttempt.objects.create(
            day=day,
            user=user,
            player=player,
            game=game,
            correct_count=8,
            score=2400,
            completed_at=timezone.now(),
        )

        html = self.client.get('/site/countries/netherlands/').content.decode()
        self.assertIn('National League', html)
        self.assertIn('Ada League', html)
        self.assertIn('2400', html)
        self.assertIn('Full National League standings', html)
        self.assertIn('/league/NL/leaderboard', html)
        self.assertNotIn('No one has played this week', html)

    def test_national_league_index_page(self):
        from django.contrib.auth.models import User

        from jizz.models import LeagueMembership

        empty = self.client.get('/site/national-league/').content.decode()
        self.assertIn('National League', empty)
        self.assertIn('Countries with players', empty)
        self.assertIn('No countries have National League players yet', empty)
        self.assertIn('href="/league"', empty)
        self.assertEqual(self.client.get('/national-league/').status_code, 301)

        user = User.objects.create_user('league-nl', password='x')
        LeagueMembership.objects.create(user=user, country=self.nl)
        cache.clear()
        html = self.client.get('/site/national-league/').content.decode()
        self.assertIn('Netherlands', html)
        self.assertIn('1 player', html)
        self.assertIn('/league/NL', html)
        self.assertIn('/site/countries/netherlands/', html)
        self.assertNotIn('No countries have National League players yet', html)

    def test_survival_index_page(self):
        from jizz.models import Game, Player, PlayerScore

        empty = self.client.get('/site/survival/').content.decode()
        self.assertIn('Survival', empty)
        self.assertIn('Country records', empty)
        self.assertIn('No Survival records yet', empty)
        self.assertIn('href="/survival"', empty)
        self.assertEqual(self.client.get('/survival-mode/').status_code, 301)

        player = Player.objects.create(name='Surv Ace', language='en')
        game = Game.objects.create(
            country=self.nl,
            level='pro',
            length=0,
            media='images',
            multiplayer=False,
            game_type=Game.GAME_TYPE_SURVIVAL,
        )
        PlayerScore.objects.create(player=player, game=game, score=900, streak=12)
        cache.clear()
        html = self.client.get('/site/survival/').content.decode()
        self.assertIn('Netherlands', html)
        self.assertIn('Record 12', html)
        self.assertIn('Surv Ace', html)
        self.assertIn('1 player', html)
        self.assertIn('/survival/scores?country=NL', html)
        self.assertNotIn('No Survival records yet', html)

    def test_bird_and_compare_pages(self):
        self.sparrow.refresh_from_db()
        self.goshawk.refresh_from_db()
        bird = self.client.get(f'/site/birds/{self.sparrow.slug}/')
        self.assertEqual(bird.status_code, 200)
        html = bird.content.decode()
        self.assertIn('Eurasian Sparrowhawk', html)
        self.assertIn('Accipiter nisus', html)
        self.assertIn('species-hero', html)
        self.assertIn('species-thumb', html)
        self.assertIn('View all photos, video and sound', html)
        self.assertIn('https://ebird.org/species/eurspa', html)
        self.assertIn('https://birdsoftheworld.org/bow/species/eurspa/cur/introduction', html)
        self.assertIn('eBird', html)
        self.assertIn('Birds of the World', html)
        self.assertIn(f'data-species-id="{self.sparrow.id}"', html)
        self.assertIn(f'/api/species/{self.sparrow.id}/', html)
        self.assertIn('Review needed', html)
        self.assertIn('community-driven', html)
        self.assertIn('Review photos', html)
        self.assertIn(f'/media-review/?species={self.sparrow.id}', html)
        self.assertNotIn('review-status is-ok', html)
        self.assertNotIn('Often mixed up with', html)
        self.assertIn('aria-current="page"', html)
        self.assertRegex(html, r'href="/site/birds/"[^>]*aria-current="page"')
        self.assertIn('>Practice</a>', html)
        self.assertIn(f'Play a quiz with {self.sparrow.name} and similar species', html)
        self.assertIn(f'/practice/species/{self.sparrow.slug}', html)
        self.assertNotIn('Start a quiz', html)
        self.assertNotIn('Practise tricky birds', html)

        game = Game.objects.create(
            country=self.nl,
            level='beginner',
            length=10,
            media='images',
            multiplayer=False,
        )
        q_sparrow = Question.objects.create(
            game=game, species=self.sparrow, number=1, sequence=1,
        )
        q_goshawk = Question.objects.create(
            game=game, species=self.goshawk, number=2, sequence=2,
        )
        for i, question, pick in (
            (0, q_sparrow, self.goshawk),
            (1, q_goshawk, self.sparrow),
        ):
            player = Player.objects.create(name=f'Mix-{i}', language='en')
            score = PlayerScore.objects.create(player=player, game=game, score=10)
            Answer.objects.create(
                player_score=score,
                question=question,
                answer=pick,
                correct=False,
            )

        cache.clear()
        html = self.client.get(f'/site/birds/{self.sparrow.slug}/').content.decode()
        self.assertIn('Often mixed up with', html)
        self.assertIn('Northern Goshawk', html)
        self.assertIn('Accipiter gentilis', html)
        low, high = (
            (self.sparrow, self.goshawk)
            if self.sparrow.id < self.goshawk.id
            else (self.goshawk, self.sparrow)
        )
        self.assertIn(f'/site/compare/{low.slug}-vs-{high.slug}/', html)
        self.assertIn(f'/site/birds/{self.goshawk.slug}/', html)

        hidden = Species.objects.create(name='Ghost Bird', name_latin='Ghostus birdus', code='ghost')
        self.assertEqual(self.client.get(f'/site/birds/{hidden.slug}/').status_code, 404)
        self.assertEqual(self.client.get('/site/birds/no-such-bird/').status_code, 404)

        low, high = (
            (self.sparrow, self.goshawk)
            if self.sparrow.id < self.goshawk.id
            else (self.goshawk, self.sparrow)
        )
        pair = f'{low.slug}-vs-{high.slug}'
        compare = self.client.get(f'/site/compare/{pair}/')
        self.assertEqual(compare.status_code, 200)
        html = compare.content.decode()
        self.assertIn('>Practice</a>', html)
        self.assertIn(f'/practice/pair/{pair}', html)
        self.assertIn(f'Play a quiz with {low.name} and {high.name}', html)
        self.assertNotIn('Start a quiz', html)
        self.assertNotIn('Practise this pair', html)
        self.assertIn('Sparrowhawks are smaller', html)
        self.assertIn('generated by AI', html)
        self.assertIn('ai-warning', html)
        self.assertIn('Submit a better description', html)
        self.assertIn('community-driven', html)
        self.assertIn('community-dialog', html)
        self.assertIn('id="login-dialog"', html)
        self.assertIn('js-open-editor', html)
        self.assertIn('birdr_open_editor', html)
        self.assertIn('contenteditable', html)
        self.assertIn('data-cmd="bold"', html)
        self.assertIn('data-cmd="italic"', html)
        self.assertIn('data-cmd="insertUnorderedList"', html)
        self.assertIn('data-cmd="insertOrderedList"', html)
        self.assertIn('copyright-protected sources', html)
        self.assertIn('I understand', html)
        self.assertIn('birdr_copyright_disclaimer_ok', html)
        self.assertIn('Discard your changes?', html)
        self.assertIn('Keep editing', html)
        self.assertIn('data-open-species-media', html)
        self.assertIn(f'/api/species/{low.id}/', html)
        self.assertIn(f'/api/species/{high.id}/', html)
        self.assertIn('species-media-dialog', html)
        self.assertIn('height="210"', html)
        self.assertNotIn('width="280"', html)

        reversed_pair = f'{high.slug}-vs-{low.slug}'
        redirect = self.client.get(f'/site/compare/{reversed_pair}/')
        self.assertEqual(redirect.status_code, 301)

    def test_bird_page_shows_reviewed_when_ten_images_accepted(self):
        self.sparrow.refresh_from_db()
        player = Player.objects.create(name='Reviewer', language='en')
        for i in range(10):
            media = Media.objects.create(
                species=self.sparrow,
                type='image',
                hide=False,
                url=f'https://example.com/sparrow-{i}.jpg',
            )
            MediaReview.objects.create(
                media=media,
                player=player,
                review_type=MediaReview.APPROVED,
            )
        html = self.client.get(f'/site/birds/{self.sparrow.slug}/').content.decode()
        self.assertIn('review-status is-ok', html)
        self.assertIn('Reviewed', html)
        self.assertNotIn('Review needed', html)
        self.assertNotIn('Review photos', html)
        self.assertNotIn(f'/media-review/?species={self.sparrow.id}', html)

    def test_tricky_birds_page_shows_missed_and_pairs(self):
        game = Game.objects.create(
            country=self.nl,
            level='beginner',
            length=10,
            media='images',
            multiplayer=False,
        )
        question = Question.objects.create(
            game=game, species=self.goshawk, number=1, sequence=1,
        )
        for i in range(10):
            player = Player.objects.create(name=f'Tricky-miss-{i}', language='en')
            score = PlayerScore.objects.create(player=player, game=game, score=10)
            Answer.objects.create(
                player_score=score,
                question=question,
                answer=self.sparrow,
                correct=False,
            )

        html = self.client.get('/site/my-tricky-birds/').content.decode()
        self.assertIn('Birds people mix up most', html)
        self.assertIn('Most missed species', html)
        self.assertIn('Confusing pairs', html)
        self.assertIn('Eurasian Sparrowhawk', html)
        self.assertIn('Northern Goshawk', html)
        self.assertIn(f'/site/birds/{self.sparrow.slug}/', html)
        low, high = (
            (self.sparrow, self.goshawk)
            if self.sparrow.id < self.goshawk.id
            else (self.goshawk, self.sparrow)
        )
        self.assertIn(f'/site/compare/{low.slug}-vs-{high.slug}/', html)
        self.assertIn('/data/quiz-mistakes/species/', html)
        self.assertIn('/data/quiz-mistakes/pairs/', html)

    @patch('jizz.marketing.country_stats.get_species_mistake_rows', return_value=[])
    @patch('jizz.marketing.country_stats.get_confusion_pair_rows', return_value=[])
    def test_tricky_birds_page_caches_mistake_queries(self, mock_pairs, mock_missed):
        url = '/site/my-tricky-birds/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(mock_missed.call_count, 1)
        self.assertEqual(mock_pairs.call_count, 1)

    @patch('jizz.marketing.views.get_confused_partners_for_species', return_value=[])
    def test_bird_page_caches_confused_species_query(self, mock_partners):
        url = f'/site/birds/{self.sparrow.slug}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(mock_partners.call_count, 1)

    def test_compare_page_without_written_comparison(self):
        extra = Species.objects.create(name='Little Gull', name_latin='Hydrocoloeus minutus', code='litgul')
        extra.refresh_from_db()
        low, high = (
            (self.sparrow, extra)
            if self.sparrow.id < extra.id
            else (extra, self.sparrow)
        )
        pair = f'{low.slug}-vs-{high.slug}'
        with patch('compare.generation.get_or_create_species_comparison') as mock_generate:
            response = self.client.get(f'/site/compare/{pair}/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(low.name, html)
        self.assertIn(high.name, html)
        self.assertIn('id="ai-generate"', html)
        self.assertIn(f'data-species-1="{low.id}"', html)
        self.assertIn(f'data-species-2="{high.id}"', html)
        self.assertIn('/api/compare/request/', html)
        self.assertIn('Birds of the World', html)
        self.assertIn('id="ai-credits-empty"', html)
        self.assertIn('/images/birdr-stressed.png', html)
        self.assertIn('id="ai-credits-empty" hidden', html)
        mock_generate.assert_not_called()

    def test_compare_page_renders_generated_markdown(self):
        extra = Species.objects.create(name='Little Gull', name_latin='Hydrocoloeus minutus', code='litgul')
        extra.refresh_from_db()
        low, high = (
            (self.sparrow, extra)
            if self.sparrow.id < extra.id
            else (extra, self.sparrow)
        )
        SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=low,
            species_2=high,
            summary='**Wing formula** is the key.',
            size_comparison='Almost the same size.',
            identification_tips='- Check primary projection\n- Listen in spring',
            detailed_comparison='',
            ai_model=comparison_model_name(),
            ai_prompt_version=comparison_prompt_version(),
        )
        pair = f'{low.slug}-vs-{high.slug}'
        response = self.client.get(f'/site/compare/{pair}/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<strong>Wing formula</strong>', html)
        self.assertIn('Identification tips', html)
        self.assertLess(html.find('In short'), html.find('Identification tips'))
        self.assertLess(html.find('Identification tips'), html.find('>Size<'))
        self.assertIn('<li>', html)
        self.assertNotIn('often mixed up', html)
        self.assertNotIn('id="ai-generate"', html)

    @patch('compare.i18n._translate_with_openai')
    def test_compare_page_auto_translates_and_caches(self, mock_tr):
        mock_tr.return_value = {
            'summary': 'Sperwers zijn kleiner, met een vierkante staart.',
            'detailed_comparison': 'Grootte, staartvorm en vlucht scheiden de twee Accipiters.',
            'identification_tips': 'Kijk naar het formaat naast andere vogels, dan de staarthoeken.',
        }
        low, high = (
            (self.sparrow, self.goshawk)
            if self.sparrow.id < self.goshawk.id
            else (self.goshawk, self.sparrow)
        )
        pair = f'{low.slug}-vs-{high.slug}'
        from compare.i18n import _translate_in_background

        # The page never waits for OpenAI: English now, translated in the background.
        with patch('compare.i18n._schedule_translation', side_effect=_translate_in_background):
            first = self.client.get(f'/nl/site/compare/{pair}/')
        self.assertEqual(first.status_code, 200)
        self.assertNotIn('Sperwers zijn kleiner', first.content.decode())
        mock_tr.assert_called_once()
        from compare.models import ComparisonTranslation

        row = ComparisonTranslation.objects.get(language='nl')
        self.assertEqual(
            row.fields['summary'],
            'Sperwers zijn kleiner, met een vierkante staart.',
        )

        second = self.client.get(f'/nl/site/compare/{pair}/')
        self.assertIn('Sperwers zijn kleiner', second.content.decode())
        mock_tr.assert_called_once()

    def test_compare_page_retries_handbook_extract(self):
        extra = Species.objects.create(name='Little Gull', name_latin='Hydrocoloeus minutus', code='litgul')
        extra.refresh_from_db()
        low, high = (
            (self.sparrow, extra)
            if self.sparrow.id < extra.id
            else (extra, self.sparrow)
        )
        SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=low,
            species_2=high,
            summary='Taken from Birds of the World identification notes.',
            identification_tips='Primary projection long versus short.',
            detailed_comparison='',
            ai_model=HANDBOOK_MODEL,
            ai_prompt_version=comparison_prompt_version(),
        )
        pair = f'{low.slug}-vs-{high.slug}'
        html = self.client.get(f'/site/compare/{pair}/').content.decode()
        self.assertIn('id="ai-generate"', html)
        self.assertIn('/api/compare/request/', html)
        self.assertIn('id="ai-credits-empty"', html)
        self.assertIn('id="ai-credits-empty" hidden', html)
        self.assertIn('/images/birdr-stressed.png', html)
        self.assertIn('I develop Motmot in my spare time', html)
        self.assertIn('info@motmot.club', html)
        self.assertNotIn('It is not a rewritten field-guide card.', html)
        self.assertNotIn('Primary projection long versus short.', html)
        pic = self.client.get('/images/birdr-stressed.png')
        self.assertEqual(pic.status_code, 200)
        self.assertTrue(pic['Content-Type'].startswith('image/'))

    def test_spa_robots_txt_points_at_marketing_sitemap(self):
        # nginx serves this file instead of Django's robots.txt when /robots.txt isn't proxied.
        spa_robots = Path(__file__).resolve().parents[2] / 'app' / 'public' / 'robots.txt'
        self.assertIn(f'Sitemap: {settings.MARKETING_URL}/sitemap.xml', spa_robots.read_text())

    def test_robots_and_sitemaps(self):
        robots = self.client.get('/robots.txt')
        self.assertEqual(robots.status_code, 200)
        text = robots.content.decode()
        self.assertIn('Disallow: /admin/', text)
        self.assertIn('Disallow: /api/', text)
        self.assertIn('Disallow: /token/', text)
        self.assertIn('Disallow: /site/my-edits/', text)
        self.assertIn('Disallow: /site/logout/', text)
        self.assertIn('Sitemap: https://motmot.club/sitemap.xml', text)

        index = self.client.get('/sitemap.xml')
        self.assertEqual(index.status_code, 200)
        self.assertIn('sitemap-pages.xml', index.content.decode())

        pages = self.client.get('/sitemap-pages.xml')
        body = pages.content.decode()
        self.assertIn('https://motmot.club/site/', body)
        self.assertIn('https://motmot.club/site/birds/', body)
        self.assertIn('https://motmot.club/site/how-it-works/', body)
        self.assertNotIn('https://motmot.club/site/bird-identification-quiz/', body)
        self.assertIn('https://motmot.club/site/flocks/', body)
        self.assertIn('https://motmot.club/site/community/', body)
        self.assertIn('https://motmot.club/site/newsletter/', body)
        self.assertIn('https://motmot.club/site/faq/', body)
        self.assertIn('https://motmot.club/site/national-league/', body)
        self.assertIn('https://motmot.club/site/survival/', body)
        self.assertNotIn('/site/my-edits/', body)

        countries = self.client.get('/sitemap-countries.xml').content.decode()
        self.assertIn('/site/countries/netherlands/', countries)
        self.assertNotIn('/site/countries/world/', countries)

        birds = self.client.get('/sitemap-birds.xml').content.decode()
        self.assertIn(f'/site/birds/{self.sparrow.slug}/', birds)

        compare = self.client.get('/sitemap-compare.xml').content.decode()
        self.assertIn('-vs-', compare)

        self.assertEqual(self.client.get('/sitemap-nope.xml').status_code, 404)
        self.assertEqual(self.client.get('/sitemap-birds.xml?page=2').status_code, 404)

    def test_region_pages_world_and_sitemap(self):
        def country(code, name, **fields):
            row, _ = Country.objects.update_or_create(code=code, defaults={'name': name, **fields})
            CountrySpecies.objects.get_or_create(country=row, species=self.sparrow)
            return row

        us = country('US', 'United States')
        country('GE', 'Georgia')
        country('US-GA', 'Georgia', kind='subnational', parent=us)
        country('US-AK', 'United States - Alaska', kind='subnational', parent=us)
        country('US-EAST', 'United States - Eastern', kind='aggregate', parent=us)
        country('NL-TX', 'Texel Bird Week', kind='specialty', parent=self.nl)

        page = self.client.get('/site/bird-quiz-by-country/').content.decode()
        self.assertIn('All the birds of the world', page)
        self.assertIn('States, provinces and regions', page)
        self.assertIn('href="/site/countries/united-states/georgia/"', page)
        self.assertIn('href="/site/countries/united-states/alaska/"', page)
        self.assertIn('href="/site/countries/united-states/eastern/"', page)
        self.assertNotIn('Texel Bird Week', page)
        self.assertIn('id="picker-country"', page)
        self.assertIn('<option value="US">', page)
        self.assertIn('"US": {"url": "/site/countries/united-states/"', page)
        self.assertIn('"url": "/site/countries/united-states/alaska/"', page)
        self.assertIn('Show all', page)
        nl_page = self.client.get('/nl/site/bird-quiz-by-country/').content.decode()
        self.assertIn('"url": "/nl/site/countries/united-states/alaska/"', nl_page)

        state = self.client.get('/site/countries/united-states/georgia/')
        self.assertEqual(state.status_code, 200)
        html = state.content.decode()
        self.assertIn('Birds of Georgia, United States', html)
        self.assertIn('href="/site/countries/united-states/"', html)
        self.assertNotIn('href="/league/US-GA"', html)
        self.assertIn(
            'Birds of United States - Eastern',
            self.client.get('/site/countries/united-states/eastern/').content.decode(),
        )
        self.assertIn('Birds of Georgia', self.client.get('/site/countries/georgia/').content.decode())
        self.assertEqual(self.client.get('/site/countries/united-states/nowhere/').status_code, 404)
        self.assertEqual(self.client.get('/site/countries/netherlands/texel-bird-week/').status_code, 404)

        us_page = self.client.get('/site/countries/united-states/').content.decode()
        self.assertIn('Quizzes for regions of United States', us_page)
        self.assertIn('href="/site/countries/united-states/alaska/"', us_page)
        # Regional lists come first, then a divider, then the states.
        eastern = us_page.index('/site/countries/united-states/eastern/')
        divider = us_page.index('class="pill-divider"', eastern)
        self.assertLess(divider, us_page.index('/site/countries/united-states/alaska/'))

        countries = self.client.get('/sitemap-countries.xml').content.decode()
        self.assertIn('https://motmot.club/site/countries/united-states/georgia/', countries)
        self.assertIn('https://motmot.club/nl/site/countries/united-states/alaska/', countries)
        self.assertNotIn('texel', countries)

    def test_order_family_and_group_pages(self):
        from jizz.models import SpeciesGroup, TaxonomicFamily, TaxonomicOrder

        order = TaxonomicOrder.objects.create(
            name_latin='Accipitriformes', name_en='Accipitriformes', name_nl='Accipitriformes',
            description_en='Birds of prey that hunt by day.',
        )
        family = TaxonomicFamily.objects.create(
            taxonomic_order=order, name_latin='Accipitridae', name_en='Hawks and Eagles', name_nl='Havikachtigen',
        )
        group = SpeciesGroup.objects.create(
            slug='hawks', ebird_name='Hawks', name_en='Hawks', name_nl='Haviken', sort_order=1,
        )
        Species.objects.filter(pk__in=[self.sparrow.pk, self.goshawk.pk]).update(
            taxonomic_family=family, taxonomic_order=order, species_group=group,
        )
        cache.clear()

        family_page = self.client.get('/site/families/accipitridae/').content.decode()
        self.assertIn('Hawks and Eagles (Accipitridae) – Bird Family | Motmot', family_page)
        self.assertIn(f'href="/site/birds/{self.sparrow.slug}/"', family_page)
        self.assertIn('href="/site/orders/accipitriformes/"', family_page)
        # The AI comparison from setUp links the two hawks.
        self.assertIn('/site/compare/', family_page)

        order_page = self.client.get('/site/orders/accipitriformes/').content.decode()
        self.assertIn('<title>Accipitriformes – Bird Order | Motmot</title>', order_page)
        self.assertIn('Birds of prey that hunt by day.', order_page)
        self.assertIn('href="/site/families/accipitridae/"', order_page)

        nl_group = self.client.get('/nl/site/groups/hawks/').content.decode()
        self.assertIn('Haviken – vogelgroep | Motmot', nl_group)
        self.assertIn(f'href="/nl/site/birds/{self.goshawk.slug}/"', nl_group)

        self.assertIn('href="/site/groups/hawks/"', self.client.get('/site/groups/').content.decode())
        self.assertEqual(self.client.get('/site/families/').status_code, 301)
        self.assertEqual(self.client.get('/site/families/nope/').status_code, 404)

        bird = self.client.get(f'/site/birds/{self.sparrow.slug}/').content.decode()
        self.assertIn('href="/site/families/accipitridae/"', bird)
        self.assertIn('href="/site/groups/hawks/"', bird)
        # Breadcrumbs run Home › Species › order › family › bird, also in the structured data.
        trail = [
            '"item": "https://motmot.club/site/birds/"',
            '"name": "Accipitriformes", "item": "https://motmot.club/site/orders/accipitriformes/"',
            '"name": "Hawks and Eagles", "item": "https://motmot.club/site/families/accipitridae/"',
            f'"item": "https://motmot.club/site/birds/{self.sparrow.slug}/"',
        ]
        positions = [bird.index(step) for step in trail]
        self.assertEqual(positions, sorted(positions))

        index = self.client.get('/sitemap.xml').content.decode()
        self.assertIn('https://motmot.club/sitemap-taxa.xml', index)
        taxa = self.client.get('/sitemap-taxa.xml').content.decode()
        self.assertIn('https://motmot.club/site/families/accipitridae/', taxa)
        self.assertIn('https://motmot.club/nl/site/groups/hawks/', taxa)

    def test_sitemaps_list_lastmod_from_page_content(self):
        from django.contrib.auth.models import User

        from compare.models import CommunityComparison, SpeciesDescription

        def at(day):
            return datetime(2026, 10, day, 12, tzinfo=dt_timezone.utc)

        description = SpeciesDescription.objects.create(
            species=self.sparrow, summary='Small hawk.', ai_model='m', ai_prompt_version='v1',
        )
        SpeciesDescription.objects.filter(pk=description.pk).update(updated=at(3))
        SpeciesComparison.objects.update(updated_at=at(5))

        origin = 'https://motmot.club'
        sparrow_path = f'/site/birds/{self.sparrow.slug}/'
        birds = _sitemap_lastmods(self.client.get('/sitemap-birds.xml').content.decode())
        self.assertEqual(birds[origin + sparrow_path], '2026-10-03')
        self.assertEqual(birds[f'{origin}/nl{sparrow_path}'], '2026-10-03')
        # No description, no timestamp: leave it out rather than make one up.
        self.assertIsNone(birds[f'{origin}/site/birds/{self.goshawk.slug}/'])

        low, high = sorted([self.sparrow, self.goshawk], key=lambda s: s.id)
        compare_loc = f'{origin}/site/compare/{low.slug}-vs-{high.slug}/'
        compare = _sitemap_lastmods(self.client.get('/sitemap-compare.xml').content.decode())
        self.assertEqual(compare[compare_loc], '2026-10-05')

        community = CommunityComparison.objects.create(
            species_low=low,
            species_high=high,
            author=User.objects.create_user(username='writer', password='x'),
            author_name='Writer',
            summary='Tail corners.',
        )
        CommunityComparison.objects.filter(pk=community.pk).update(updated=at(9))
        compare = _sitemap_lastmods(self.client.get('/sitemap-compare.xml').content.decode())
        self.assertEqual(compare[compare_loc], '2026-10-09')

        index = _sitemap_lastmods(self.client.get('/sitemap.xml').content.decode())
        self.assertEqual(index[f'{origin}/sitemap-birds.xml'], '2026-10-03')
        self.assertEqual(index[f'{origin}/sitemap-compare.xml'], '2026-10-09')
        self.assertIsNone(index[f'{origin}/sitemap-countries.xml'])
        self.assertIsNone(index[f'{origin}/sitemap-taxa.xml'])

    def test_sitemap_index_lastmod_is_per_page(self):
        paths = [f'/site/birds/bird-{i}/' for i in range(3)]
        lastmods = {paths[0]: datetime(2026, 10, 1).date(), paths[1]: datetime(2026, 10, 7).date()}
        with patch.dict('jizz.marketing.sitemaps.SECTIONS', {'birds': lambda: paths}), \
                patch.dict('jizz.marketing.sitemaps.LASTMODS', {'birds': lambda: lastmods}), \
                patch('jizz.marketing.sitemaps.PATHS_PER_SITEMAP', 2):
            index = _sitemap_lastmods(self.client.get('/sitemap.xml').content.decode())
            self.assertEqual(index['https://motmot.club/sitemap-birds.xml'], '2026-10-07')
            self.assertIsNone(index['https://motmot.club/sitemap-birds.xml?page=2'])

    def test_large_sitemap_sections_are_split_into_pages(self):
        paths = [f'/site/birds/bird-{i}/' for i in range(5)]
        with patch.dict('jizz.marketing.sitemaps.SECTIONS', {'birds': lambda: paths}), \
                patch('jizz.marketing.sitemaps.PATHS_PER_SITEMAP', 2):
            index = self.client.get('/sitemap.xml').content.decode()
            self.assertIn('https://motmot.club/sitemap-birds.xml', index)
            self.assertIn('https://motmot.club/sitemap-birds.xml?page=2', index)
            self.assertIn('https://motmot.club/sitemap-birds.xml?page=3', index)
            self.assertNotIn('sitemap-birds.xml?page=4', index)

            first = self.client.get('/sitemap-birds.xml').content.decode()
            self.assertIn('/site/birds/bird-1/', first)
            self.assertNotIn('/site/birds/bird-2/', first)
            last = self.client.get('/sitemap-birds.xml?page=3').content.decode()
            self.assertIn('/site/birds/bird-4/', last)
            self.assertNotIn('/site/birds/bird-3/', last)
            self.assertEqual(self.client.get('/sitemap-birds.xml?page=4').status_code, 404)

    def test_localized_marketing_pages(self):
        en = self.client.get('/site/')
        self.assertEqual(en.status_code, 200)
        html = en.content.decode()
        self.assertIn('lang="en"', html)
        self.assertIn('hreflang="nl"', html)
        self.assertIn('https://motmot.club/nl/site/', html)
        self.assertIn('hreflang="pt-BR"', html)
        self.assertIn('https://motmot.club/pt-BR/site/', html)
        self.assertIn('hreflang="x-default"', html)
        self.assertIn('id="nav-lang"', html)
        self.assertIn('Nederlands', html)
        self.assertIn('日本語', html)
        self.assertEqual(en['Content-Language'], 'en')

        nl = self.client.get('/nl/site/')
        self.assertEqual(nl.status_code, 200)
        dutch = nl.content.decode()
        self.assertIn('lang="nl"', dutch)
        self.assertIn('Verbeter je vogelkennis.', dutch)
        self.assertIn('Hoe het werkt', dutch)
        self.assertIn('href="/nl/site/how-it-works/"', dutch)
        self.assertIn('href="/nl/site/community/"', dutch)
        self.assertIn('href="/nl/site/newsletter/"', dutch)
        self.assertIn('https://motmot.club/nl/site/', dutch)
        self.assertNotIn('https://motmot.club/nl/nl/site/', dutch)
        self.assertEqual(nl['Content-Language'], 'nl')

        how_nl = self.client.get('/nl/site/how-it-works/').content.decode()
        self.assertIn('Begin met een fotoquiz', how_nl)
        self.assertIn('href="/nl/site/my-tricky-birds/"', how_nl)

        community_nl = self.client.get('/nl/site/community/').content.decode()
        self.assertIn('Vertel het verder', community_nl)
        self.assertIn('href="/nl/site/newsletter/"', community_nl)
        self.assertIn('Facebookgroep', community_nl)
        self.assertIn('ticket in op GitHub', community_nl)
        self.assertIn('Steun Motmot', community_nl)
        self.assertIn('trakteren op een kopje koffie', community_nl)
        self.assertIn('Zet een store-review', community_nl)
        self.assertIn('Review in de App Store', community_nl)
        self.assertIn('12 beoordelingen', community_nl)

        newsletter_nl = self.client.get('/nl/site/newsletter/').content.decode()
        self.assertIn('Zet het in de clubnieuwsbrief', newsletter_nl)
        self.assertIn('Wil je tussen excursies door scherper worden in vogelherkenning', newsletter_nl)
        self.assertIn('Maak een account als je je voortgang wilt bewaren.', newsletter_nl)
        self.assertIn('Meer media', newsletter_nl)
        self.assertNotIn(
            'If you want to get sharper at identification between outings',
            newsletter_nl,
        )

    def test_help_template_strings_are_in_catalogs(self):
        import ast
        import re
        from pathlib import Path

        from jizz.marketing.catalogs import CATALOGS

        html_files = [
            Path(__file__).resolve().parents[1] / 'templates' / 'marketing' / '_help.html',
            Path(__file__).resolve().parents[1] / 'templates' / 'marketing' / '_store_scores.html',
            Path(__file__).resolve().parents[1] / 'templates' / 'marketing' / 'community.html',
            Path(__file__).resolve().parents[1] / 'templates' / 'marketing' / '_newsletter_example.html',
            Path(__file__).resolve().parents[1] / 'templates' / 'marketing' / 'newsletter.html',
        ]
        pattern = re.compile(
            r'\{%\s*mt\s+("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')',
            re.S,
        )
        messages = []
        for html_path in html_files:
            html = html_path.read_text()
            for raw in pattern.findall(html):
                msgid = ast.literal_eval(raw)
                if msgid not in messages:
                    messages.append(msgid)
        self.assertGreater(len(messages), 20)
        missing = [
            msgid
            for msgid in messages
            if any(msgid not in catalog for catalog in CATALOGS.values())
        ]
        self.assertEqual(missing, [])

        ja = self.client.get('/ja/site/faq/')
        self.assertEqual(ja.status_code, 200)
        self.assertIn('lang="ja"', ja.content.decode())
        self.assertIn('Motmotは無料ですか？', ja.content.decode())

        redirect = self.client.get('/en/site/how-it-works/')
        self.assertEqual(redirect.status_code, 301)
        self.assertEqual(redirect['Location'], '/site/how-it-works/')

        bare = self.client.get('/de')
        self.assertEqual(bare.status_code, 301)
        self.assertEqual(bare['Location'], '/de/site/')

        pages = self.client.get('/sitemap-pages.xml').content.decode()
        self.assertIn('https://motmot.club/nl/site/', pages)
        self.assertIn('hreflang="ja"', pages)
        self.assertIn('xmlns:xhtml', pages)

    def test_localized_country_and_species_names(self):
        from jizz.models import Language, SpeciesName, TaxonomicFamily

        Language.objects.get_or_create(code='nl', defaults={'name': 'Dutch'})
        SpeciesName.objects.create(
            species=self.sparrow, language_id='nl', name='Sperwer',
        )
        SpeciesName.objects.create(
            species=self.goshawk, language_id='nl', name='Havik',
        )
        family = TaxonomicFamily.objects.create(
            name_latin='Accipitridae',
            name_en='Hawks, eagles and kites',
            name_nl='Haviken',
        )
        self.sparrow.taxonomic_family = family
        self.sparrow.save(update_fields=['taxonomic_family'])

        en_country = self.client.get('/site/countries/netherlands/').content.decode()
        self.assertIn('Birds of Netherlands', en_country)
        self.assertIn('>Netherlands</li>', en_country)
        self.assertNotIn('Vogels van Nederland', en_country)

        nl_country = self.client.get('/nl/site/countries/netherlands/').content.decode()
        self.assertIn('Vogels van Nederland', nl_country)
        self.assertIn('>Nederland</li>', nl_country)
        self.assertNotIn('Birds of Netherlands', nl_country)
        self.assertNotIn('Vogels van Netherlands', nl_country)

        landing_nl = self.client.get('/nl/site/').content.decode()
        self.assertIn('</span> Nederland</a>', landing_nl)
        self.assertIn('Wat is Motmot?', landing_nl)
        self.assertIn('inloggen met Google', landing_nl)

        bird_en = self.client.get(f'/site/birds/{self.sparrow.slug}/').content.decode()
        self.assertIn('Eurasian Sparrowhawk', bird_en)
        self.assertNotIn('Sperwer', bird_en)

        bird_nl = self.client.get(f'/nl/site/birds/{self.sparrow.slug}/').content.decode()
        self.assertIn('Sperwer', bird_nl)
        self.assertNotIn('Eurasian Sparrowhawk', bird_nl)
        self.assertIn('Haviken', bird_nl)

        search = self.client.get('/nl/site/birds/', {'q': 'sperwer'}).content.decode()
        self.assertIn('Sperwer', search)
        self.assertIn(f'/nl/site/birds/{self.sparrow.slug}/', search)

        birds_nl = self.client.get('/nl/site/birds/').content.decode()
        self.assertIn('Sperwer', birds_nl)
        self.assertIn('Havik', birds_nl)
        self.assertIn('Haviken', birds_nl)

        low, high = (
            (self.sparrow, self.goshawk)
            if self.sparrow.id < self.goshawk.id
            else (self.goshawk, self.sparrow)
        )
        compare = self.client.get(
            f'/nl/site/compare/{low.slug}-vs-{high.slug}/'
        ).content.decode()
        self.assertIn('Sperwer', compare)
        self.assertIn('Havik', compare)
        self.assertNotIn('Eurasian Sparrowhawk', compare)
        self.assertNotIn('Northern Goshawk', compare)

    @override_settings(
        GOOGLE_SITE_VERIFICATION='google-token',
        BING_SITE_VERIFICATION='bing-token',
        YANDEX_VERIFICATION='yandex-token',
    )
    def test_verification_meta(self):
        html = self.client.get('/site/').content.decode()
        self.assertIn('google-site-verification', html)
        self.assertIn('google-token', html)
        self.assertIn('msvalidate.01', html)
        self.assertIn('bing-token', html)
        self.assertIn('yandex-verification', html)
        self.assertIn('yandex-token', html)

    def test_indexnow_key_file_is_in_the_spa_root(self):
        # nginx serves app/public at the site root; IndexNow fetches the key from there.
        key_file = Path(__file__).resolve().parents[2] / 'app' / 'public' / f'{settings.INDEXNOW_KEY}.txt'
        self.assertEqual(key_file.read_text().strip(), settings.INDEXNOW_KEY)


class MarketingStaticPagesTests(TestCase):
    def test_about_page_tells_the_story(self):
        response = self.client.get('/site/page/about/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('About Motmot', html)
        self.assertIn('Hi, I’m Loek!', html)
        self.assertIn('Costa Rica', html)
        self.assertIn('href="https://github.com/birdr-app/birdr"', html)
        self.assertIn('Xeno-canto', html)
        self.assertIn('https://motmot.club/site/page/about/', html)
        landing = self.client.get('/site/').content.decode()
        self.assertIn('/site/page/about/', landing)
        primary = landing.split('<nav class="site"', 1)[1].split('</nav>', 1)[0]
        self.assertNotIn('/site/page/about/', primary)
        self.assertNotIn('/site/page/privacy/', primary)

    def test_privacy_page_in_dutch(self):
        html = self.client.get('/nl/site/page/privacy/').content.decode()
        self.assertIn('Privacybeleid', html)
        self.assertIn('mailto:info@motmot.club', html)
        self.assertNotIn('birdr.pro', html)
        self.assertIn('Engelse versie', html)
        self.assertNotIn('If a translation differs', self.client.get('/site/page/privacy/').content.decode())

    def test_no_editor_for_staff(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('cms-home', password='x', is_staff=True)
        self.client.force_login(user)
        for path in ('/site/', '/site/page/about/'):
            html = self.client.get(path).content.decode()
            self.assertNotIn('id="cms-bar"', html)
            self.assertNotIn('canEditServer', html)
        self.assertEqual(self.client.get('/api/marketing-pages/').status_code, 404)

    def test_old_page_addresses(self):
        self.assertEqual(self.client.get('/site/page/draft/').status_code, 404)
        self.assertEqual(self.client.get('/site/page/')['Location'], '/site/')
        self.assertEqual(self.client.get('/nl/site/page/')['Location'], '/nl/site/')
        sitemap = self.client.get('/sitemap-pages.xml').content.decode()
        self.assertIn('https://motmot.club/site/page/about/', sitemap)
        self.assertIn('https://motmot.club/site/page/privacy/', sitemap)
        self.assertEqual(self.client.get('/page/about/').status_code, 301)
        self.assertEqual(self.client.get('/page/about/')['Location'], '/site/page/about/')
        self.assertEqual(self.client.get('/site/about/').status_code, 301)
        self.assertEqual(self.client.get('/site/about/')['Location'], '/site/page/about/')


class MarketingCompareCommunityTests(TestCase):
    def setUp(self):
        MarketingPagesTests.setUp(self)

    def _compare_pair(self):
        low, high = (
            (self.sparrow, self.goshawk)
            if self.sparrow.id < self.goshawk.id
            else (self.goshawk, self.sparrow)
        )
        return low, high, f'{low.slug}-vs-{high.slug}'

    def test_compare_community_submit_edit_and_delete(self):
        from django.contrib.auth import get_user_model
        from compare.models import CommunityComparison

        User = get_user_model()
        author = User.objects.create_user('ada', password='x', first_name='Ada', last_name='Lovelace')
        other = User.objects.create_user('bob', password='x', first_name='Bob')
        staff = User.objects.create_user('mod', password='x', is_staff=True)
        low, high, pair = self._compare_pair()
        url = f'/site/compare/{pair}/community/'
        page = f'/site/compare/{pair}/'

        response = self.client.post(url, {'summary': 'Look at the tail.'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])
        self.assertEqual(CommunityComparison.objects.count(), 0)

        self.client.force_login(author)
        empty = self.client.post(url, {'summary': '  '})
        self.assertEqual(empty.status_code, 200)
        self.assertIn('at least one section', empty.content.decode())

        saved = self.client.post(url, {'summary': 'Square tail vs bulky bulk.', 'identification_tips': 'Start with size.'})
        self.assertEqual(saved.status_code, 302)
        self.assertIn('notice=saved', saved['Location'])
        html = self.client.get(page).content.decode()
        self.assertIn('Square tail vs bulky bulk.', html)
        self.assertIn('By Ada Lovelace', html)
        self.assertNotIn('generated by AI', html)
        self.assertIn('Show the AI-generated comparison', html)
        self.assertIn('Edit this description', html)

        ai = self.client.get(page, {'source': 'ai'}).content.decode()
        self.assertIn('generated by AI', ai)
        self.assertIn('Sparrowhawks are smaller', ai)
        self.assertIn('Show the community comparison', ai)

        self.client.logout()
        self.client.force_login(other)
        blocked = self.client.post(url, {'summary': 'Bob rewrite'})
        self.assertEqual(blocked.status_code, 200)
        self.assertIn('already published', blocked.content.decode())
        self.assertEqual(CommunityComparison.objects.get().summary, 'Square tail vs bulky bulk.')
        other_page = self.client.get(page).content.decode()
        self.assertRegex(other_page, r'js-manage"[^>]*hidden')
        self.assertRegex(other_page, r'js-editor"[^>]*hidden')

        self.client.logout()
        self.client.force_login(author)
        edited = self.client.post(url, {'summary': 'Ada revised the tail mark.'})
        self.assertEqual(edited.status_code, 302)
        self.assertEqual(CommunityComparison.objects.get().summary, 'Ada revised the tail mark.')

        self.client.logout()
        self.client.force_login(staff)
        staff_page = self.client.get(page).content.decode()
        self.assertIn('Delete description', staff_page)
        staff_edit = self.client.post(url, {'summary': 'Moderator tweak.'})
        self.assertEqual(staff_edit.status_code, 302)
        row = CommunityComparison.objects.get()
        self.assertEqual(row.summary, 'Moderator tweak.')
        self.assertEqual(row.author, author)
        self.assertEqual(row.author_name, 'Ada Lovelace')
        deleted = self.client.post(url, {'action': 'delete'})
        self.assertEqual(deleted.status_code, 302)
        self.assertEqual(CommunityComparison.objects.count(), 0)
        restored = self.client.get(page).content.decode()
        self.assertIn('generated by AI', restored)
        self.assertIn('Sparrowhawks are smaller', restored)

    def test_compare_community_jwt_submit(self):
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import RefreshToken
        from compare.models import CommunityComparison

        User = get_user_model()
        user = User.objects.create_user('jwt-user', password='x', first_name='Jules')
        token = str(RefreshToken.for_user(user).access_token)
        low, high, pair = self._compare_pair()
        response = self.client.post(
            f'/site/compare/{pair}/community/',
            {'summary': 'JWT community text.'},
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(response.status_code, 302)
        row = CommunityComparison.objects.get()
        self.assertEqual(row.summary, 'JWT community text.')
        self.assertEqual(row.author, user)

    def test_my_edits_page_and_json(self):
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import RefreshToken
        from compare.models import CommunityComparison
        from media.models import MediaReview

        User = get_user_model()
        guest = self.client.get('/site/my-edits/')
        self.assertEqual(guest.status_code, 200)
        guest_html = guest.content.decode()
        self.assertIn('community-driven', guest_html)
        self.assertIn('name="robots"', guest_html)
        self.assertIn('noindex', guest_html)
        self.assertIn('id="edits-login"', guest_html)
        self.assertIn('Log in to see', guest_html)
        self.assertEqual(self.client.get('/site/my-edits/?format=json').status_code, 401)

        author = User.objects.create_user(
            'editorada', password='x', first_name='Ada', last_name='Lovelace'
        )
        self.sparrow.refresh_from_db()
        self.goshawk.refresh_from_db()
        low, high, pair = self._compare_pair()
        CommunityComparison.objects.create(
            species_low=low,
            species_high=high,
            author=author,
            author_name='Ada Lovelace',
            summary='Square tail vs bulky bulk.',
            published=True,
        )
        MediaReview.objects.create(
            media=Media.objects.filter(species=self.sparrow).first(),
            user=author,
            review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=Media.objects.filter(species=self.goshawk).first(),
            user=author,
            review_type=MediaReview.REJECTED,
        )
        self.client.force_login(author)
        html = self.client.get('/site/my-edits/').content.decode()
        self.assertIn('Square tail vs bulky bulk.', html)
        self.assertIn(f'/site/compare/{pair}/', html)
        self.assertIn(low.name, html)
        self.assertIn(high.name, html)
        self.assertIn('id="review-accepted">1<', html)
        self.assertIn('id="review-rejected">1<', html)

        data = self.client.get('/site/my-edits/?format=json').json()
        self.assertEqual(data['accepted'], 1)
        self.assertEqual(data['rejected'], 1)
        self.assertEqual(len(data['edits']), 1)
        self.assertEqual(data['edits'][0]['url'], f'/site/compare/{pair}/')

        self.client.logout()
        token = str(RefreshToken.for_user(author).access_token)
        jwt = self.client.get(
            '/site/my-edits/?format=json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(jwt.status_code, 200)
        self.assertEqual(jwt.json()['accepted'], 1)

        logout = self.client.post('/site/logout/')
        self.assertEqual(logout.status_code, 302)
        self.assertEqual(logout['Location'], '/site/')


def _started_token(seconds_ago=3):
    import time
    from django.core.signing import Signer

    return Signer(salt='marketing-feedback').sign(str(int(time.time()) - seconds_ago))


class MarketingFeedbackFormTests(TestCase):
    def setUp(self):
        self.ratings_patcher = patch(
            'jizz.store_ratings.get_store_ratings',
            return_value={'ios': None, 'android': None},
        )
        self.ratings_patcher.start()
        self.addCleanup(self.ratings_patcher.stop)

    def test_community_shows_form(self):
        html = self.client.get('/site/community/').content.decode()
        self.assertIn('name="comment"', html)
        self.assertIn('name="website"', html)
        self.assertIn('action="/site/feedback/"', html)

    def test_valid_submit_saves_and_emails(self):
        from django.core import mail
        from jizz.models import Feedback

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(
                '/site/feedback/',
                {
                    'comment': 'Love the quizzes',
                    'name': 'Ada',
                    'email': 'ada@example.com',
                    'started': _started_token(),
                    'next': '/site/',
                    'website': '',
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/site/?sent=1#help')
        feedback = Feedback.objects.get()
        self.assertEqual(feedback.comment, 'Love the quizzes')
        self.assertEqual(feedback.contact_name, 'Ada')
        self.assertEqual(feedback.contact_email, 'ada@example.com')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ['Ada <ada@example.com>'])

    def test_suggest_game_anchor_redirect(self):
        response = self.client.post(
            '/site/feedback/',
            {
                'comment': 'A memory game for calls',
                'started': _started_token(),
                'next': '/site/',
                'anchor': 'suggest-game',
                'website': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/site/?sent=1#suggest-game')

    def test_honeypot_is_dropped(self):
        from jizz.models import Feedback

        response = self.client.post(
            '/site/feedback/',
            {
                'comment': 'spam',
                'started': _started_token(),
                'website': 'http://bots.example',
                'next': '/site/',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/site/?sent=1#help')
        self.assertEqual(Feedback.objects.count(), 0)

    def test_instant_submit_is_dropped(self):
        from jizz.models import Feedback

        response = self.client.post(
            '/site/feedback/',
            {
                'comment': 'too fast',
                'started': _started_token(seconds_ago=0),
                'next': '/site/',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Feedback.objects.count(), 0)

    def test_missing_comment(self):
        from jizz.models import Feedback

        response = self.client.post(
            '/site/feedback/',
            {'comment': '  ', 'started': _started_token(), 'next': '/site/'},
        )
        self.assertEqual(response['Location'], '/site/?sent=missing#help')
        self.assertEqual(Feedback.objects.count(), 0)

    def test_invalid_email(self):
        from jizz.models import Feedback

        response = self.client.post(
            '/site/feedback/',
            {
                'comment': 'Hi',
                'email': 'not-an-email',
                'started': _started_token(),
                'next': '/site/',
            },
        )
        self.assertEqual(response['Location'], '/site/?sent=email#help')
        self.assertEqual(Feedback.objects.count(), 0)



class MarketingUpdatesTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from jizz.models import Update

        author = User.objects.create_user(username='author', password='x')
        self.update = Update.objects.create(
            title_en='Birdr is now Motmot!',
            title_nl='Birdr heet nu Motmot!',
            body_en='{"delta":"","html":"<p>A new name.</p><script>alert(1)</script>"}',
            body_nl='{"delta":"","html":"<p>Een nieuwe naam.</p>"}',
            user=author,
        )
        self.draft = Update.objects.create(
            title_en='Secret draft',
            body_en='{"delta":"","html":"<p>Not yet.</p>"}',
            user=author,
            published=False,
        )

    def test_index_lists_published_updates_only(self):
        response = self.client.get('/site/updates/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Birdr is now Motmot!', html)
        self.assertIn('A new name.', html)
        self.assertIn(f'/site/updates/{self.update.pk}/', html)
        self.assertNotIn('Secret draft', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('/site/updates/', self.client.get('/site/').content.decode())

    def test_dutch_index_uses_the_dutch_text(self):
        html = self.client.get('/nl/site/updates/').content.decode()
        self.assertIn('Birdr heet nu Motmot!', html)
        self.assertIn('Een nieuwe naam.', html)
        self.assertIn('november', html)

    @patch('jizz.update_i18n._translate_with_openai')
    def test_missing_translation_falls_back_to_english_without_calling_openai(self, translate):
        html = self.client.get('/de/site/updates/').content.decode()
        self.assertIn('Birdr is now Motmot!', html)
        translate.assert_not_called()

    def test_update_page(self):
        response = self.client.get(f'/site/updates/{self.update.pk}/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<h1>Birdr is now Motmot!</h1>', html)
        self.assertIn(f'https://motmot.club/site/updates/{self.update.pk}/', html)
        self.assertIn(f'/open/update/{self.update.pk}/', html)

    def test_draft_update_page_is_not_found(self):
        self.assertEqual(self.client.get(f'/site/updates/{self.draft.pk}/').status_code, 404)

    def test_sitemap_lists_updates(self):
        body = self.client.get('/sitemap-pages.xml').content.decode()
        self.assertIn('https://motmot.club/site/updates/', body)
        self.assertIn(f'https://motmot.club/site/updates/{self.update.pk}/', body)
        self.assertNotIn(f'/site/updates/{self.draft.pk}/', body)

    def test_sitemap_lastmod_for_updates(self):
        from jizz.models import Update

        Update.objects.filter(pk=self.update.pk).update(created=datetime(2026, 10, 4, 9, tzinfo=dt_timezone.utc))
        Update.objects.filter(pk=self.draft.pk).update(created=datetime(2026, 10, 30, 9, tzinfo=dt_timezone.utc))
        lastmods = _sitemap_lastmods(self.client.get('/sitemap-pages.xml').content.decode())
        self.assertEqual(lastmods[f'https://motmot.club/site/updates/{self.update.pk}/'], '2026-10-04')
        # The draft is not on the index page, so it does not date it.
        self.assertEqual(lastmods['https://motmot.club/site/updates/'], '2026-10-04')
        self.assertIsNone(lastmods['https://motmot.club/site/'])
        index = _sitemap_lastmods(self.client.get('/sitemap.xml').content.decode())
        self.assertEqual(index['https://motmot.club/sitemap-pages.xml'], '2026-10-04')


class IndexNowSubmitTests(TestCase):
    def test_submits_every_locale_of_the_pages(self):
        from io import StringIO

        from django.core.management import call_command

        with patch('jizz.management.commands.indexnow_submit.requests.post') as post:
            post.return_value.status_code = 202
            call_command('indexnow_submit', '--section', 'pages', stdout=StringIO())
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['host'], 'motmot.club')
        self.assertEqual(payload['key'], settings.INDEXNOW_KEY)
        self.assertEqual(payload['keyLocation'], f'https://motmot.club/{settings.INDEXNOW_KEY}.txt')
        self.assertIn('https://motmot.club/site/', payload['urlList'])
        self.assertIn('https://motmot.club/nl/site/', payload['urlList'])

    def test_dry_run_sends_nothing(self):
        from io import StringIO

        from django.core.management import call_command

        with patch('jizz.management.commands.indexnow_submit.requests.post') as post:
            call_command('indexnow_submit', '--dry-run', stdout=StringIO())
        post.assert_not_called()


class MarketingTranslationCoverageTests(SimpleTestCase):
    def test_translate_calls_have_every_locale(self):
        # A missing msgid falls back to English, which went unnoticed on page titles.
        import ast
        import re

        from jizz.marketing.catalogs import CATALOGS

        root = Path(__file__).resolve().parents[2]
        sources = [*sorted((root / 'jizz' / 'marketing').glob('*.py')), root / 'compare' / 'views.py']
        missing = []
        for path in sources:
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
                msg = node.args[0]
                if name not in ('translate', 'lookup') or not isinstance(msg, ast.Constant):
                    continue
                if not isinstance(msg.value, str):
                    continue
                placeholders = set(re.findall(r'\{(\w+)\}', msg.value))
                for locale, catalog in CATALOGS.items():
                    text = catalog.get(msg.value)
                    if text is None or set(re.findall(r'\{(\w+)\}', text)) != placeholders:
                        missing.append(f'{path.name}:{node.lineno} {locale} {msg.value[:60]!r}')
        self.assertEqual(missing, [])
