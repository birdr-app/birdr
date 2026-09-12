from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from jizz.data_user_stats import MOST_GAMES_PAGE_SIZE, games_per_user_rows, media_reviews_per_user_rows
from jizz.models import Country, CountrySpecies, Game, Player, PlayerScore, Species
from jizz.tests.taxonomy_helpers import make_species_with_taxonomy
from media.models import Media, MediaReview

User = get_user_model()


class DataViewsTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code="NL", defaults={"name": "Netherlands"})[0]

        self.sp_passer1 = make_species_with_taxonomy(
            name="House Sparrow",
            name_latin="Passer domesticus",
            code="SP01",
            tax_order="Passeriformes",
            tax_family="Passeridae",
        )
        self.sp_passer2 = make_species_with_taxonomy(
            name="Tree Sparrow",
            name_latin="Passer montanus",
            code="SP02",
            tax_order="Passeriformes",
            tax_family="Passeridae",
        )
        self.sp_anser = make_species_with_taxonomy(
            name="Greylag Goose",
            name_latin="Anser anser",
            code="AN01",
            tax_order="Anseriformes",
            tax_family="Anatidae",
        )
        self.sp_branta = make_species_with_taxonomy(
            name="Canada Goose",
            name_latin="Branta canadensis",
            code="AN02",
            tax_order="Anseriformes",
            tax_family="Anatidae",
        )
        self.sp_endemic = make_species_with_taxonomy(
            name="Endemic duck",
            name_latin="Endemic duckus",
            code="AN03",
            tax_order="Anseriformes",
            tax_family="Anatidae",
        )
        self.sp_introduced = make_species_with_taxonomy(
            name="Introduced goose",
            name_latin="Introduced gooseus",
            code="AN04",
            tax_order="Anseriformes",
            tax_family="Anatidae",
        )

        for sp in (
            self.sp_passer1,
            self.sp_passer2,
            self.sp_anser,
            self.sp_branta,
            self.sp_endemic,
            self.sp_introduced,
        ):
            status = "endemic" if sp is self.sp_endemic else "introduced" if sp is self.sp_introduced else "native"
            CountrySpecies.objects.create(country=self.country, species=sp, status=status)

    def test_data_index_public(self):
        res = Client().get(reverse("data-index"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Birdr data")
        self.assertContains(res, reverse("data-taxon-orders"))
        self.assertContains(res, reverse("data-games-played"))
        self.assertContains(res, reverse("data-marketing-website"))
        self.assertContains(res, reverse("data-most-reviews"))
        self.assertContains(res, "favicon-32x32.png")
        self.assertContains(res, "/images/birdr-icon.png")
        self.assertContains(res, "padding: 0.85rem 1.5rem 0")

    def test_taxon_orders_global_counts(self):
        res = Client().get(reverse("data-taxon-orders"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Passeriformes")
        self.assertContains(res, "Anseriformes")

    def test_taxon_orders_country_filter_excludes_introduced(self):
        res = Client().get(reverse("data-taxon-orders"), {"country": "NL"})
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        self.assertIn("Native", content)
        self.assertIn("Endemic", content)
        self.assertNotIn("Introduced goose", content)

    def test_taxon_families_country_filter(self):
        res = Client().get(reverse("data-taxon-families"), {"country": "NL"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Anatidae")
        self.assertContains(res, "Passeridae")

    def test_taxon_orders_sort_by_species_count_desc(self):
        for i in range(2):
            sp = make_species_with_taxonomy(
                name=f"Extra Sparrow {i}",
                name_latin=f"Passer extra{i}",
                code=f"SPX{i}",
                tax_order="Passeriformes",
                tax_family="Passeridae",
            )
            CountrySpecies.objects.create(country=self.country, species=sp, status="native")
        res = Client().get(
            reverse("data-taxon-orders"),
            {"country": "NL", "sort": "species_count", "dir": "desc"},
        )
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        tbody = content.split("<tbody>")[1].split("</tbody>")[0]
        passer_pos = tbody.index("Passeriformes")
        anser_pos = tbody.index("Anseriformes")
        self.assertLess(passer_pos, anser_pos)

    def test_taxon_families_sort_by_order(self):
        res = Client().get(
            reverse("data-taxon-families"),
            {"sort": "order", "dir": "asc"},
        )
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        anat_pos = content.index("Anatidae")
        passer_pos = content.index("Passeridae")
        self.assertLess(anat_pos, passer_pos)


class GamesPlayedViewsTests(TestCase):
    def test_games_played_page_public(self):
        res = Client().get(reverse("data-games-played"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "games-played-chart")
        self.assertContains(res, "games-world-map")
        self.assertContains(res, 'id="most-games"')
        self.assertContains(res, "Most games per user")
        self.assertNotContains(res, 'id="challenge-leaderboard"')

    def test_games_played_api(self):
        res = Client().get(
            reverse("data-games-played-api"),
            {"start": "2026-01-01", "end": "2026-01-31", "granularity": "month"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["granularity"], "month")
        self.assertIn("series", data)
        self.assertIn("by_country", data)
        self.assertIn("country_map", data)
        self.assertNotIn("leaderboard", data)


class CountryChallengeLeaderboardViewsTests(TestCase):
    def test_leaderboard_page_public(self):
        res = Client().get(reverse("data-country-challenge-leaderboard"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Country Challenge leaderboard")
        self.assertContains(res, "challenge-leaderboard")

    def test_leaderboard_api(self):
        res = Client().get(reverse("data-country-challenge-leaderboard-api"))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("leaderboard", data)
        self.assertIsInstance(data["leaderboard"], list)

    def test_leaderboard_api_endpoint(self):
        res = Client().get(reverse("birdr-journey-leaderboard"))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("leaderboard", data)
        self.assertIn("no-store", res["Cache-Control"])


class MostGamesViewsTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code="NL", defaults={"name": "Netherlands"})[0]
        self.user = User.objects.create_user("ada", "ada@example.com", "secret123")
        self.player_a = Player.objects.create(name="Ada One", language="en", user=self.user)
        self.player_b = Player.objects.create(name="Ada Two", language="en", user=self.user)
        self.guest = Player.objects.create(name="Guest Bird", language="en")

    def _play(self, player, n, when=None):
        for _ in range(n):
            game = Game.objects.create(
                country=self.country,
                level="beginner",
                length=5,
                media="images",
                host=player,
            )
            if when is not None:
                aware = timezone.make_aware(datetime.combine(when, datetime.min.time()))
                Game.objects.filter(pk=game.pk).update(created=aware)
            PlayerScore.objects.create(player=player, game=game, score=1)

    def _most_games_tbody(self, content: str) -> str:
        start = content.index('id="most-games"')
        return content[start:].split("<tbody>", 1)[1].split("</tbody>", 1)[0]

    def test_most_games_url_redirects_to_games_played(self):
        res = Client().get(reverse("data-most-games"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], reverse("data-games-played") + "#most-games")

    def test_most_games_section_on_games_played_page(self):
        self._play(self.player_a, 2)
        self._play(self.player_b, 1)
        self._play(self.guest, 1)
        res = Client().get(reverse("data-games-played"))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        self.assertIn("most-games", content)
        self.assertIn("First game", content)
        self.assertIn("Ada One", content)
        self.assertIn("Guest Bird", content)
        ada_pos = content.index("Ada One")
        guest_pos = content.index("Guest Bird")
        self.assertLess(ada_pos, guest_pos)
        tbody = self._most_games_tbody(content)
        self.assertEqual(tbody.count("<tr>"), 2)
        self.assertNotIn('id="most-games-load-more"', content)

    def test_most_games_section_limits_to_top_20_with_load_more(self):
        for i in range(MOST_GAMES_PAGE_SIZE + 1):
            player = Player.objects.create(name=f"Ranked {i:02d}", language="en")
            self._play(player, MOST_GAMES_PAGE_SIZE + 1 - i)
        res = Client().get(reverse("data-games-played"))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        tbody = self._most_games_tbody(content)
        self.assertEqual(tbody.count("<tr>"), MOST_GAMES_PAGE_SIZE)
        self.assertIn("Ranked 00", tbody)
        self.assertNotIn("Ranked 20", tbody)
        self.assertIn("Ranked 20", content)
        self.assertIn('id="most-games-load-more"', content)
        self.assertIn(f"Showing {MOST_GAMES_PAGE_SIZE} of {MOST_GAMES_PAGE_SIZE + 1}", content)

    def test_linked_players_count_as_one_user(self):
        self._play(self.player_a, 2, when=date(2024, 3, 12))
        self._play(self.player_b, 1, when=date(2026, 1, 4))
        rows = games_per_user_rows()
        ada = next(row for row in rows if row["name"] == "Ada One")
        self.assertEqual(ada["games"], 3)
        self.assertEqual(ada["first_played"], date(2024, 3, 12))

    def test_same_player_name_is_grouped(self):
        guest_two = Player.objects.create(name="guest bird", language="en")
        self._play(self.guest, 2, when=date(2025, 6, 1))
        self._play(guest_two, 3, when=date(2024, 1, 9))
        rows = games_per_user_rows()
        grouped = [row for row in rows if row["name"].casefold() == "guest bird"]
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["games"], 5)
        self.assertEqual(grouped[0]["first_played"], date(2024, 1, 9))
        self.assertEqual(grouped[0]["name"], "guest bird")


class MostReviewsViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reviewer", "rev@example.com", "secret123")
        self.player = Player.objects.create(name="Reviewer", language="en", user=self.user)
        self.guest = Player.objects.create(name="Guest Reviewer", language="en")
        self.species = Species.objects.create(name="S", name_latin="S", code="MR01")

    def _media(self, suffix):
        return Media.objects.create(
            species=self.species,
            type="image",
            url=f"https://example.com/{suffix}.jpg",
            source="test",
        )

    def test_most_reviews_page_public(self):
        MediaReview.objects.create(
            media=self._media("a"),
            user=self.user,
            review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=self._media("b"),
            player=self.player,
            review_type=MediaReview.REJECTED,
        )
        MediaReview.objects.create(
            media=self._media("c"),
            player=self.guest,
            review_type=MediaReview.NOT_SURE,
        )
        res = Client().get(reverse("data-most-reviews"))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        self.assertIn("most-reviews", content)
        self.assertIn("Reviewer", content)
        self.assertIn("Guest Reviewer", content)
        self.assertIn("Coverage by country", content)
        self.assertIn("Top reviewers", content)
        self.assertIn("By source", content)
        self.assertIn("reviews-by-month-chart", content)
        self.assertIn("reviews-by-month-data", content)
        self.assertIn("10+ approved photos", content)
        self.assertNotIn("Species with a review", content)

    def test_review_overview_counts_species_ready_at_10_approved_or_fully_reviewed(self):
        from jizz.data_review_stats import review_overview
        from jizz.marketing.pages import MEDIA_REVIEWED_APPROVED_COUNT

        ready_few = Species.objects.create(name="Few Ready", name_latin="Few f", code="fewrdy")
        not_ready_few = Species.objects.create(name="Few Partial", name_latin="Few p", code="fewprt")
        ready_many = Species.objects.create(name="Many Ready", name_latin="Many r", code="manyrd")
        not_ready_many = Species.objects.create(name="Many Partial", name_latin="Many p", code="manypr")

        for suffix, species in (("a", ready_few), ("b", ready_few)):
            MediaReview.objects.create(
                media=Media.objects.create(
                    species=species,
                    type="image",
                    url=f"https://example.com/few-{suffix}.jpg",
                    source="test",
                ),
                player=self.player,
                review_type=MediaReview.APPROVED,
            )
        partial = Media.objects.create(
            species=not_ready_few,
            type="image",
            url="https://example.com/partial-a.jpg",
            source="test",
        )
        Media.objects.create(
            species=not_ready_few,
            type="image",
            url="https://example.com/partial-b.jpg",
            source="test",
        )
        MediaReview.objects.create(
            media=partial,
            player=self.player,
            review_type=MediaReview.APPROVED,
        )
        for i in range(MEDIA_REVIEWED_APPROVED_COUNT):
            MediaReview.objects.create(
                media=Media.objects.create(
                    species=ready_many,
                    type="image",
                    url=f"https://example.com/many-ready-{i}.jpg",
                    source="test",
                ),
                player=self.player,
                review_type=MediaReview.APPROVED,
            )
        for i in range(MEDIA_REVIEWED_APPROVED_COUNT - 1):
            MediaReview.objects.create(
                media=Media.objects.create(
                    species=not_ready_many,
                    type="image",
                    url=f"https://example.com/many-partial-{i}.jpg",
                    source="test",
                ),
                player=self.player,
                review_type=MediaReview.APPROVED,
            )
        Media.objects.create(
            species=not_ready_many,
            type="image",
            url="https://example.com/many-partial-extra.jpg",
            source="test",
        )

        overview = review_overview()
        self.assertEqual(overview["species_with_photos"], 4)
        self.assertEqual(overview["species_ready"], 2)
        self.assertEqual(overview["species_ready_pct"], 50.0)

    def test_reviews_by_month_is_a_filled_12_month_series(self):
        from datetime import datetime

        from jizz.data_review_stats import reviews_by_month_rows
        from jizz.games_played_stats import default_date_range

        review = MediaReview.objects.create(
            media=self._media("month"),
            user=self.user,
            review_type=MediaReview.APPROVED,
        )
        start, _end = default_date_range()
        when = start.replace(day=15)
        MediaReview.objects.filter(pk=review.pk).update(
            created=timezone.make_aware(datetime.combine(when, datetime.min.time()))
        )
        rows = reviews_by_month_rows()
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0]["month"], start.isoformat())
        self.assertEqual(sum(row["total"] for row in rows), 1)
        self.assertEqual(rows[0]["total"], 1)

    def test_reviews_merge_user_and_player_and_split_types(self):
        MediaReview.objects.create(
            media=self._media("a"),
            user=self.user,
            review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=self._media("b"),
            player=self.player,
            review_type=MediaReview.REJECTED,
        )
        MediaReview.objects.create(
            media=self._media("c"),
            player=self.guest,
            review_type=MediaReview.NOT_SURE,
        )
        rows = media_reviews_per_user_rows()
        by_name = {row["name"]: row for row in rows}
        self.assertEqual(by_name["Reviewer"]["total"], 2)
        self.assertEqual(by_name["Reviewer"]["approved"], 1)
        self.assertEqual(by_name["Reviewer"]["rejected"], 1)
        self.assertEqual(by_name["Reviewer"]["not_sure"], 0)
        self.assertEqual(by_name["Guest Reviewer"]["total"], 1)
        self.assertEqual(by_name["Guest Reviewer"]["not_sure"], 1)
        self.assertLess(rows.index(by_name["Reviewer"]), rows.index(by_name["Guest Reviewer"]))


class ReviewCoverageStatsTests(TestCase):
    def setUp(self):
        self.nl = Country.objects.get_or_create(code="NL", defaults={"name": "Netherlands"})[0]
        self.de = Country.objects.get_or_create(code="DE", defaults={"name": "Germany"})[0]
        self.ma = Country.objects.get_or_create(code="US-MA", defaults={"name": "Massachusetts"})[0]
        self.bird = Species.objects.create(name="Robin", name_latin="Erithacus rubecula", code="eurrob")
        self.other = Species.objects.create(name="Jay", name_latin="Garrulus glandarius", code="eurjay")
        CountrySpecies.objects.create(country=self.nl, species=self.bird, status="native")
        CountrySpecies.objects.create(country=self.de, species=self.other, status="native")
        CountrySpecies.objects.create(country=self.ma, species=self.bird, status="native")
        self.player = Player.objects.create(name="Pat", language="en")

    def _photo(self, species, suffix, *, hide=False, source="wikimedia"):
        return Media.objects.create(
            species=species,
            type="image",
            url=f"https://example.com/{suffix}.jpg",
            source=source,
            hide=hide,
        )

    def test_country_coverage_uses_checklist_photos(self):
        from jizz.data_review_stats import country_review_coverage_rows

        kept = self._photo(self.bird, "nl-a")
        self._photo(self.bird, "nl-b")
        self._photo(self.other, "de-a")
        self._photo(self.bird, "hidden", hide=True)
        MediaReview.objects.create(
            media=kept,
            player=self.player,
            review_type=MediaReview.APPROVED,
        )
        rows = {row["code"]: row for row in country_review_coverage_rows()}
        self.assertEqual(rows["NL"]["photos"], 2)
        self.assertEqual(rows["NL"]["reviewed"], 1)
        self.assertEqual(rows["NL"]["pct"], 50.0)
        self.assertEqual(rows["NL"]["species_with_photos"], 1)
        self.assertEqual(rows["NL"]["species_with_review"], 1)
        self.assertEqual(rows["DE"]["photos"], 1)
        self.assertEqual(rows["DE"]["reviewed"], 0)
        self.assertEqual(rows["DE"]["pct"], 0.0)
        self.assertNotIn("US-MA", rows)

    def test_unknown_status_country_is_omitted(self):
        from jizz.data_review_stats import country_review_coverage_rows

        xx = Country.objects.create(code="XX", name="Placeholder Isle")
        CountrySpecies.objects.create(country=xx, species=self.bird, status="unknown")
        self._photo(self.bird, "xx-only")
        rows = {row["code"]: row for row in country_review_coverage_rows()}
        self.assertNotIn("XX", rows)
        self.assertIn("NL", rows)

    def test_country_coverage_ordered_by_species_pct_desc(self):
        from jizz.data_review_stats import country_review_coverage_rows

        fr = Country.objects.get_or_create(code="FR", defaults={"name": "France"})[0]
        be = Country.objects.get_or_create(code="BE", defaults={"name": "Belgium"})[0]
        fr_bird = Species.objects.create(name="French Robin", name_latin="Erithacus gallicus", code="frrob1")
        be_common = Species.objects.create(name="Belgian Jay", name_latin="Garrulus belgica", code="bejay1")
        be_rare = Species.objects.create(name="Belgian Wren", name_latin="Troglodytes belgica", code="bewre1")
        CountrySpecies.objects.create(country=fr, species=fr_bird, status="native")
        CountrySpecies.objects.create(country=be, species=be_common, status="native")
        CountrySpecies.objects.create(country=be, species=be_rare, status="native")
        reviewed = self._photo(fr_bird, "fr-reviewed")
        self._photo(fr_bird, "fr-unreviewed")
        for i in range(10):
            photo = self._photo(be_common, f"be-reviewed-{i}")
            MediaReview.objects.create(
                media=photo,
                player=self.player,
                review_type=MediaReview.APPROVED,
            )
        self._photo(be_rare, "be-unreviewed")
        MediaReview.objects.create(
            media=reviewed,
            player=self.player,
            review_type=MediaReview.APPROVED,
        )
        rows = country_review_coverage_rows()
        by_code = {row["code"]: row for row in rows}
        self.assertGreater(by_code["FR"]["species_pct"], by_code["BE"]["species_pct"])
        self.assertLess(by_code["FR"]["pct"], by_code["BE"]["pct"])
        self.assertLess(rows.index(by_code["FR"]), rows.index(by_code["BE"]))

    def test_show_more_reviewers_when_more_than_ten(self):
        for i in range(12):
            player = Player.objects.create(name=f"Reviewer {i}", language="en")
            MediaReview.objects.create(
                media=self._photo(self.bird, f"r{i}"),
                player=player,
                review_type=MediaReview.APPROVED,
            )
        res = Client().get(reverse("data-most-reviews"))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode()
        self.assertIn("Show all 12 reviewers", content)
        self.assertIn("extra-reviewer", content)
        self.assertIn("By source", content)
        self.assertIn("Wikimedia", content)
        self.assertIn('href="/media-review/NL"', content)

