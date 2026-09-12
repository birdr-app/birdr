"""Public marketing pages, sitemap and robots."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

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

    def test_landing_title_canonical_and_json_ld(self):
        response = self.client.get('/site/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Birdr – Free Bird Identification Quiz &amp; Training App', html)
        self.assertIn('Improve your birding skills.', html)
        self.assertIn('What is Birdr?', html)
        self.assertIn('sign in with Google so Birdr can create your account', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn('https://birdr.pro/site/', html)
        self.assertIn('WebApplication', html)
        self.assertIn('MobileApplication', html)
        self.assertNotIn('FAQPage', html)
        self.assertIn('href="/site/community/"', html)
        self.assertIn('href="/site/faq/"', html)
        self.assertIn('href="/site/newsletter/"', html)
        self.assertIn('How you can help', html)
        self.assertIn('Read the FAQ', html)
        self.assertIn('Support Birdr', html)
        self.assertIn('https://github.com/sponsors/birdr-app', html)
        self.assertEqual(html.count('class="btn btn-support"'), 2)
        self.assertIn('id="support-birdr"', html)
        self.assertIn('There is no funding behind it right now', html)
        self.assertIn('Donating is one way', html)
        self.assertIn('Write about funding or a partnership', html)
        self.assertIn('Kudos to the developer!', html)
        self.assertIn('data-typewriter', html)
        self.assertIn('Special+Elite', html)
        self.assertIn('Bombay Natural History Society, India', html)
        self.assertIn('Kent Ornithological Society, United Kingdom', html)
        self.assertIn('BirdLife Finland (BirdLife Suomi), Finland', html)
        self.assertIn('Japan Bird Research Association, Japan', html)
        self.assertIn('info@birdr.pro', html)
        self.assertIn('https://www.facebook.com/groups/birdrcommunity', html)
        self.assertIn('https://github.com/birdr-app/birdr/issues', html)
        self.assertIn('Get it on Google Play', html)
        self.assertIn('Or play a quiz in the browser', html)
        self.assertIn('href="/play"', html)
        self.assertIn('/images/birdr-quiz.png', html)
        self.assertIn('What you can play', html)
        self.assertIn('Sound quizzes', html)
        self.assertIn('passerine sound quizzes', html)
        self.assertIn('Multiplayer', html)
        self.assertIn('two or more players', html)
        self.assertIn('Faster correct answers score more points', html)
        self.assertIn('High scores', html)
        self.assertIn('See how you rank', html)
        self.assertIn('href="/scores/"', html)
        self.assertIn('My checklist', html)
        self.assertIn('named correctly in your country', html)
        self.assertIn('href="/checklist"', html)

    def test_header_uses_birdr_icon_and_favicon(self):
        html = self.client.get('/site/').content.decode()
        self.assertIn('favicon-32x32.png', html)
        self.assertIn('/images/birdr-anime.gif', html)
        self.assertIn('class="brand-icon"', html)
        self.assertIn('padding: 8px 20px 0', html)
        icon = self.client.get('/images/birdr-anime.gif')
        self.assertEqual(icon.status_code, 200)
        self.assertIn('image/gif', icon['Content-Type'])
        favicon = self.client.get('/favicon-32x32.png')
        self.assertEqual(favicon.status_code, 200)

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
                self.assertIn(f'https://birdr.pro{path}', html)
                self.assertIn('<title>', html)

        how = self.client.get('/site/how-it-works/').content.decode()
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
        self.assertIn('/images/birdr-tricky-birds.png', tricky)
        self.assertIn('/images/birdr-tricky-practice.png', tricky)
        self.assertIn('/images/birdr-tricky-results.png', tricky)
        self.assertIn('Your tricky pairs', tricky)
        self.assertIn('Practise a pair', tricky)
        self.assertIn('See when a pair is fixed', tricky)
        for path in (
            '/images/birdr-tricky-birds.png',
            '/images/birdr-tricky-practice.png',
            '/images/birdr-tricky-results.png',
        ):
            shot = self.client.get(path)
            self.assertEqual(shot.status_code, 200, path)
            self.assertEqual(shot['Content-Type'], 'image/png')

        flocks = self.client.get('/site/flocks/').content.decode()
        self.assertIn('Flocks: quizzes for bird clubs', flocks)
        self.assertIn('/flocks/intro', flocks)

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
        self.assertIn('helps other birders find Birdr', community)
        self.assertIn('Review on the App Store', community)
        self.assertIn('Review on Google Play', community)
        self.assertIn('action=write-review', community)
        self.assertIn('class="store-score"', community)
        self.assertIn('>4.8<', community)
        self.assertIn('>4.6<', community)
        self.assertIn('12 ratings', community)
        self.assertIn('9 ratings', community)
        self.assertIn('Support Birdr', community)
        self.assertIn('https://github.com/sponsors/birdr-app', community)
        self.assertIn('btn-support', community)
        self.assertIn('sponsor Birdr on GitHub', community)
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
        self.assertIn('apps.apple.com/us/app/birdr', newsletter)
        self.assertIn('play.google.com/store/apps/details?id=pro.birdr.app', newsletter)
        self.assertIn('/images/birdr-new-game.png', newsletter)
        self.assertIn('/images/birdr-photo-quiz.png', newsletter)
        self.assertIn('/images/birdr-species-review.png', newsletter)
        self.assertIn('/images/birdr-country-challenge.png', newsletter)
        self.assertIn('/images/birdr-tricky-birds.png', newsletter)
        self.assertIn('/images/birdr-tricky-practice.png', newsletter)
        self.assertIn('/images/birdr-tricky-results.png', newsletter)
        copy_start = newsletter.index('id="newsletter-copy-body"')
        copy_end = newsletter.index('id="newsletter-more-heading"')
        copied = newsletter[copy_start:copy_end]
        self.assertIn('/images/birdr-photo-quiz.png', copied)
        self.assertIn('/images/birdr-new-game.png', copied)
        self.assertIn('/images/birdr-species-review.png', copied)
        self.assertNotIn('/images/birdr-tricky-birds.png', copied)
        self.assertNotIn('/images/birdr-country-challenge.png', copied)
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
        self.assertIn('Is Birdr free?', faq)
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
        self.assertIn('/media-review/NL', html)
        self.assertIn('Review Netherlands photos', html)
        self.assertIn('Spread the word', html)
        self.assertIn('/site/newsletter/', html)
        self.assertNotIn('Example newsletter item', html)
        self.assertNotIn('How people play', html)
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
        self.assertIn('Most missed birds', html)
        self.assertIn('Eurasian Sparrowhawk', html)
        self.assertIn('Confusing pairs', html)
        self.assertIn('vs', html)
        self.assertIn('/data/quiz-mistakes/species/?country=NL', html)
        self.assertIn('/data/quiz-mistakes/pairs/?country=NL', html)

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
        first = self.client.get(f'/nl/site/compare/{pair}/')
        self.assertEqual(first.status_code, 200)
        html = first.content.decode()
        self.assertIn('Sperwers zijn kleiner', html)
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
        self.assertIn('I develop Birdr in my spare time', html)
        self.assertIn('info@birdr.pro', html)
        self.assertNotIn('It is not a rewritten field-guide card.', html)
        self.assertNotIn('Primary projection long versus short.', html)
        pic = self.client.get('/images/birdr-stressed.png')
        self.assertEqual(pic.status_code, 200)
        self.assertTrue(pic['Content-Type'].startswith('image/'))

    def test_robots_and_sitemaps(self):
        robots = self.client.get('/robots.txt')
        self.assertEqual(robots.status_code, 200)
        text = robots.content.decode()
        self.assertIn('Disallow: /admin/', text)
        self.assertIn('Disallow: /api/', text)
        self.assertIn('Disallow: /token/', text)
        self.assertIn('Disallow: /site/my-edits/', text)
        self.assertIn('Disallow: /site/logout/', text)
        self.assertIn('Sitemap: https://birdr.pro/sitemap.xml', text)

        index = self.client.get('/sitemap.xml')
        self.assertEqual(index.status_code, 200)
        self.assertIn('sitemap-pages.xml', index.content.decode())

        pages = self.client.get('/sitemap-pages.xml')
        body = pages.content.decode()
        self.assertIn('https://birdr.pro/site/', body)
        self.assertIn('https://birdr.pro/site/birds/', body)
        self.assertIn('https://birdr.pro/site/how-it-works/', body)
        self.assertNotIn('https://birdr.pro/site/bird-identification-quiz/', body)
        self.assertIn('https://birdr.pro/site/flocks/', body)
        self.assertIn('https://birdr.pro/site/community/', body)
        self.assertIn('https://birdr.pro/site/newsletter/', body)
        self.assertIn('https://birdr.pro/site/faq/', body)
        self.assertNotIn('/site/my-edits/', body)

        countries = self.client.get('/sitemap-countries.xml').content.decode()
        self.assertIn('/site/countries/netherlands/', countries)
        self.assertNotIn('/site/countries/world/', countries)

        birds = self.client.get('/sitemap-birds.xml').content.decode()
        self.assertIn(f'/site/birds/{self.sparrow.slug}/', birds)

        compare = self.client.get('/sitemap-compare.xml').content.decode()
        self.assertIn('-vs-', compare)

    def test_localized_marketing_pages(self):
        en = self.client.get('/site/')
        self.assertEqual(en.status_code, 200)
        html = en.content.decode()
        self.assertIn('lang="en"', html)
        self.assertIn('hreflang="nl"', html)
        self.assertIn('https://birdr.pro/nl/site/', html)
        self.assertIn('hreflang="pt-BR"', html)
        self.assertIn('https://birdr.pro/pt-BR/site/', html)
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
        self.assertIn('https://birdr.pro/nl/site/', dutch)
        self.assertNotIn('https://birdr.pro/nl/nl/site/', dutch)
        self.assertEqual(nl['Content-Language'], 'nl')

        how_nl = self.client.get('/nl/site/how-it-works/').content.decode()
        self.assertIn('Begin met een fotoquiz', how_nl)
        self.assertIn('href="/nl/site/my-tricky-birds/"', how_nl)

        community_nl = self.client.get('/nl/site/community/').content.decode()
        self.assertIn('Vertel het verder', community_nl)
        self.assertIn('href="/nl/site/newsletter/"', community_nl)
        self.assertIn('Facebookgroep', community_nl)
        self.assertIn('ticket in op GitHub', community_nl)
        self.assertIn('Steun Birdr', community_nl)
        self.assertIn('sponsoren op GitHub', community_nl)
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
        self.assertIn('Birdrは無料ですか？', ja.content.decode())

        redirect = self.client.get('/en/site/how-it-works/')
        self.assertEqual(redirect.status_code, 301)
        self.assertEqual(redirect['Location'], '/site/how-it-works/')

        bare = self.client.get('/de')
        self.assertEqual(bare.status_code, 301)
        self.assertEqual(bare['Location'], '/de/site/')

        pages = self.client.get('/sitemap-pages.xml').content.decode()
        self.assertIn('https://birdr.pro/nl/site/', pages)
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
        self.assertIn('>Nederland</a>', landing_nl)
        self.assertIn('Wat is Birdr?', landing_nl)
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

    @override_settings(GOOGLE_SITE_VERIFICATION='google-token', BING_SITE_VERIFICATION='bing-token')
    def test_verification_meta(self):
        html = self.client.get('/site/').content.decode()
        self.assertIn('google-site-verification', html)
        self.assertIn('google-token', html)
        self.assertIn('msvalidate.01', html)
        self.assertIn('bing-token', html)


class MarketingCmsTests(TestCase):
    def test_seeded_about_page(self):
        response = self.client.get('/site/page/about/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('About Birdr', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn('https://birdr.pro/site/page/about/', html)
        landing = self.client.get('/site/').content.decode()
        self.assertIn('/site/page/about/', landing)
        primary = landing.split('<nav class="site"', 1)[1].split('</nav>', 1)[0]
        self.assertNotIn('/site/page/about/', primary)
        self.assertNotIn('/site/page/privacy/', primary)

    def test_unpublished_is_404(self):
        from jizz.models import MarketingPage
        MarketingPage.objects.create(
            title='Draft',
            slug='draft',
            body='<p>Secret</p>',
            published=False,
        )
        self.assertEqual(self.client.get('/site/page/draft/').status_code, 404)

    def test_staff_can_see_unpublished(self):
        from django.contrib.auth import get_user_model
        from jizz.models import MarketingPage
        MarketingPage.objects.create(
            title='Draft',
            slug='draft',
            body='<p>Secret</p>',
            published=False,
        )
        user = get_user_model().objects.create_user('cms-staff', password='x', is_staff=True)
        self.client.force_login(user)
        response = self.client.get('/site/page/draft/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Secret', response.content.decode())
        self.assertIn('canEditServer = true', response.content.decode())

    def test_staff_sees_editor_flag_on_landing(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('cms-home', password='x', is_staff=True)
        self.client.force_login(user)
        html = self.client.get('/site/').content.decode()
        self.assertIn('canEditServer = true', html)
        self.assertIn('id="cms-bar"', html)

    def test_page_index_and_sitemap(self):
        html = self.client.get('/site/page/').content.decode()
        self.assertIn('/site/page/about/', html)
        sitemap = self.client.get('/sitemap-pages.xml').content.decode()
        self.assertIn('https://birdr.pro/site/page/about/', sitemap)
        self.assertIn('https://birdr.pro/site/page/privacy/', sitemap)
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

