import math
import uuid
from datetime import timedelta
from random import randint, shuffle, random

from django.db import models, transaction, connection
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Count, Sum, Q
from django.db.utils import OperationalError, ProgrammingError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.functional import lazy
from django.utils.timezone import now
from shortuuid.django_fields import ShortUUIDField

try:
    from django_quill.fields import QuillField
except ImportError:
    QuillField = models.TextField  # fallback if django-quill-editor not installed


class Country(models.Model):
    KIND_COUNTRY = 'country'
    KIND_SUBNATIONAL = 'subnational'
    KIND_AGGREGATE = 'aggregate'
    KIND_SPECIALTY = 'specialty'
    KIND_CHOICES = [
        (KIND_COUNTRY, 'Country'),
        (KIND_SUBNATIONAL, 'Subnational'),
        (KIND_AGGREGATE, 'Aggregate'),
        (KIND_SPECIALTY, 'Specialty'),
    ]
    HEMISPHERE_NORTH = 'north'
    HEMISPHERE_SOUTH = 'south'
    HEMISPHERE_CHOICES = [
        (HEMISPHERE_NORTH, 'Northern'),
        (HEMISPHERE_SOUTH, 'Southern'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, primary_key=True)
    codes = models.CharField(max_length=400, null=True, blank=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
        help_text='Sovereign country this region belongs to (e.g. US-MA → US).',
    )
    kind = models.CharField(
        max_length=16,
        default=KIND_COUNTRY,
        choices=KIND_CHOICES,
        db_index=True,
    )
    hemisphere = models.CharField(
        max_length=8,
        default=HEMISPHERE_NORTH,
        choices=HEMISPHERE_CHOICES,
        help_text='Used to map calendar seasons to months.',
    )

    @property
    def count(self):
        return self.countryspecies.count()

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.code

    class Meta:
        verbose_name = 'country'
        verbose_name_plural = 'countries'
        ordering = ['name']


class Question(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    game = models.ForeignKey('jizz.Game', related_name='questions', on_delete=models.CASCADE)
    species = models.ForeignKey('jizz.Species', related_name='questions', on_delete=models.CASCADE)
    options = models.ManyToManyField('jizz.Species', through='jizz.QuestionOption')
    number = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    done = models.BooleanField(default=False)
    sequence = models.IntegerField(default=1)
    media = models.ForeignKey(
        'media.Media',
        null=True,
        blank=True,
        related_name='locked_questions',
        on_delete=models.PROTECT,
        help_text='When set, play always uses this exact media asset (pregenerated games).',
    )

    def __str__(self):
        return f'{self.game} - {self.species}'


class QuestionMediaReady(models.Model):
    """Client reports when primary media finished loading; scoring time uses ready_at instead of question.created."""

    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='question_media_ready')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='media_ready')
    ready_at = models.DateTimeField()

    class Meta:
        unique_together = [('player', 'question')]

    def __str__(self):
        return f'{self.player} Q{self.question_id} @ {self.ready_at}'


class QuestionOption(models.Model):
    question = models.ForeignKey('jizz.Question', on_delete=models.CASCADE)
    species = models.ForeignKey('jizz.Species', on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']


class TaxonomicOrder(models.Model):
    name_latin = models.CharField(max_length=200, unique=True)
    name_en = models.CharField(max_length=200)
    name_nl = models.CharField(max_length=200)
    description_en = models.TextField(blank=True, default='')
    description_nl = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name_latin']
        verbose_name = 'taxonomic order'
        verbose_name_plural = 'taxonomic orders'

    def __str__(self):
        return self.name_latin


class TaxonomicFamily(models.Model):
    taxonomic_order = models.ForeignKey(
        TaxonomicOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='families',
    )
    name_latin = models.CharField(max_length=200, unique=True)
    name_en = models.CharField(max_length=200)
    name_nl = models.CharField(max_length=200)
    description_en = models.TextField(blank=True, default='')
    description_nl = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['name_latin']
        verbose_name = 'taxonomic family'
        verbose_name_plural = 'taxonomic families'

    def __str__(self):
        return self.name_latin


class TaxonomicGenus(models.Model):
    taxonomic_family = models.ForeignKey(
        TaxonomicFamily,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='genera',
    )
    name_latin = models.CharField(max_length=200, unique=True)
    name_en = models.CharField(max_length=200, blank=True, default='')
    name_nl = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['name_latin']
        verbose_name = 'taxonomic genus'
        verbose_name_plural = 'taxonomic genera'

    def __str__(self):
        return self.name_latin


class SpeciesGroup(models.Model):
    """Birder-facing group (shorebirds, wood-warblers), from eBird sppgroups."""

    slug = models.SlugField(max_length=80, unique=True)
    ebird_name = models.CharField(max_length=200, unique=True)
    name_en = models.CharField(max_length=200)
    name_nl = models.CharField(max_length=200)
    name_es = models.CharField(max_length=200, blank=True, default='')
    name_fr = models.CharField(max_length=200, blank=True, default='')
    name_de = models.CharField(max_length=200, blank=True, default='')
    name_it = models.CharField(max_length=200, blank=True, default='')
    name_pt_br = models.CharField(max_length=200, blank=True, default='')
    name_ja = models.CharField(max_length=200, blank=True, default='')
    sort_order = models.PositiveIntegerField(db_index=True, default=0)
    description_en = models.TextField(blank=True, default='')
    description_nl = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['sort_order', 'name_en']
        verbose_name = 'species group'
        verbose_name_plural = 'species groups'

    def __str__(self):
        return self.name_en

    def display_name(self, locale: str = 'en') -> str:
        from jizz.services.species_groups import group_name_for_locale

        return group_name_for_locale(self, locale)


class Species(models.Model):
    name = models.CharField(max_length=200)
    name_latin = models.CharField(max_length=200)
    name_nl = models.CharField(max_length=200, null=True, blank=True)
    tax_family_en = models.CharField('Family english (old)', max_length=200, null=True, blank=True)
    tax_family = models.CharField('Family (old)', max_length=200, null=True, blank=True)
    tax_order = models.CharField('Order (old)', max_length=200, null=True, blank=True)

    taxonomic_order = models.ForeignKey(
        TaxonomicOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='species',
    )
    taxonomic_family = models.ForeignKey(
        TaxonomicFamily,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='species',
    )
    taxonomic_genus = models.ForeignKey(
        TaxonomicGenus,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='species',
    )
    species_group = models.ForeignKey(
        SpeciesGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='species',
    )
    tax_ordering = models.FloatField(null=True, blank=True, db_index=True)
    code = models.CharField(max_length=10)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    @property
    def tax_order(self):
        return self.taxonomic_order.name_latin if self.taxonomic_order_id else None

    @property
    def tax_family(self):
        return self.taxonomic_family.name_latin if self.taxonomic_family_id else None

    @property
    def tax_family_en(self):
        return self.taxonomic_family.name_en if self.taxonomic_family_id else None

    @property
    def filtered_media(self):
        """Media that are not rejected. Used as fallback when no approved media exist."""
        return self.media.exclude(reviews__review_type='rejected')

    def _eligible_media(self, media_type):
        """
        Media for game use: approved only, or if none approved then not rejected.
        Ordered by id so index (question.number) is stable.
        """
        approved = self.media.filter(
            type=media_type
        ).filter(reviews__review_type='approved').distinct()
        if approved.exists():
            return approved.order_by('id')
        return self.media.filter(
            type=media_type
        ).exclude(reviews__review_type='rejected').order_by('id')

    @property
    def images(self):
        return self._eligible_media('image')

    @property
    def videos(self):
        return self._eligible_media('video')

    @property
    def sounds(self):
        return self._eligible_media('audio')

    class Meta:
        verbose_name = 'species'
        verbose_name_plural = 'species'
        ordering = ['id']

    def __str__(self):
        return self.name


class SpeciesIllustration(models.Model):
    """AI-generated field-guide style drawing (white background), one per species."""

    STATUS_PENDING = 'pending'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    species = models.OneToOneField(
        Species,
        on_delete=models.CASCADE,
        related_name='illustration',
    )
    image = models.ImageField(
        upload_to='species_illustrations/',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    model_name = models.CharField(max_length=64, blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'species illustration'
        verbose_name_plural = 'species illustrations'

    def __str__(self):
        return f'Illustration for {self.species_id} ({self.status})'


class Language(models.Model):
    code = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Page(models.Model):
    """Simple CMS page for Help content. Content is Quill rich text (delta JSON); supports images and formatting."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    content = QuillField(blank=True)
    show = models.BooleanField(default=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class MarketingPage(models.Model):
    """Public marketing CMS page at /site/page/<slug>/, editable by staff on the site."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    meta_description = models.CharField(max_length=320, blank=True)
    body = models.TextField(blank=True, help_text='HTML body shown on the public marketing site.')
    published = models.BooleanField(default=True)
    show_in_nav = models.BooleanField(default=False)
    nav_label = models.CharField(max_length=80, blank=True)
    nav_order = models.PositiveSmallIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nav_order', 'title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from jizz.marketing.pages import cms_path
        return cms_path(self.slug)

    def nav_text(self):
        return self.nav_label or self.title


class SpeciesName(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)


def _taxonomy_tables_ready():
    try:
        return (
            'jizz_taxonomicorder' in connection.introspection.table_names()
            and 'jizz_taxonomicfamily' in connection.introspection.table_names()
            and 'jizz_taxonomicgenus' in connection.introspection.table_names()
        )
    except OperationalError:
        return False


def _species_group_table_ready():
    try:
        return 'jizz_speciesgroup' in connection.introspection.table_names()
    except OperationalError:
        return False


MIN_TAX_FILTER_SPECIES = 4


def get_tax_order_choices(country=None):
    if not _taxonomy_tables_ready():
        return []
    try:
        qs = TaxonomicOrder.objects.all()
        if country is not None:
            qs = qs.filter(species__countryspecies__country=country)
        tax_orders = (
            qs.annotate(count=Count('species', distinct=True))
            .filter(count__gte=MIN_TAX_FILTER_SPECIES)
            .order_by('name_latin')
        )
        return [
            (o.name_latin, f"{o.name_latin} ({o.count})")
            for o in tax_orders
        ]
    except (ProgrammingError, OperationalError):
        return []


def get_tax_family_choices(country=None):
    if not _taxonomy_tables_ready():
        return []
    try:
        qs = TaxonomicFamily.objects.all()
        if country is not None:
            qs = qs.filter(species__countryspecies__country=country)
        families = (
            qs.annotate(count=Count('species', distinct=True))
            .filter(count__gte=MIN_TAX_FILTER_SPECIES)
            .order_by('name_latin')
        )
        return [
            (f.name_latin, f"{f.name_latin} - {f.name_en} ({f.count})")
            for f in families
        ]
    except (ProgrammingError, OperationalError):
        return []


def get_species_group_choices(country=None):
    if not _species_group_table_ready():
        return []
    try:
        qs = SpeciesGroup.objects.all()
        if country is not None:
            qs = qs.filter(species__countryspecies__country=country)
        groups = (
            qs.annotate(count=Count('species', distinct=True))
            .filter(count__gte=MIN_TAX_FILTER_SPECIES)
            .order_by('sort_order', 'name_en')
        )
        return [
            (g.slug, f"{g.name_en} ({g.count})")
            for g in groups
        ]
    except (ProgrammingError, OperationalError):
        return []


class Game(models.Model):
    """
    Represents a game session in the Birdr application.
    
    A game contains:
    - Configuration: country, level, length, media type, filters
    - Questions: Generated on-demand as the game progresses
    - Player scores: Tracked for multiplayer games
    - State: ended flag indicates completion
    
    Game Lifecycle:
    1. Created via POST /api/games/ with configuration
    2. Questions generated lazily via add_question() method
    3. Progresses through questions until sequence > length
    4. Marked as ended when all questions completed
    
    See docs/GAME_LIFECYCLE.md for complete documentation.
    """
    MEDIA_CHOICES = [
        ('images', 'Images'),
        ('video', 'Video'),
        ('audio', 'Audio'),
    ]

    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ]

    country = models.ForeignKey('jizz.Country', on_delete=models.SET_NULL, null=True)
    language = models.CharField(max_length=100, default='en')
    token = ShortUUIDField(
        length=8,
        max_length=10,
        alphabet="abcdefghijklmnopqrstuvwxyz",
    )
    created = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=100)
    multiplayer = models.BooleanField(default=False)
    length = models.IntegerField(default=0)
    media = models.CharField(max_length=10, default='images', choices=MEDIA_CHOICES)
    repeat = models.BooleanField(default=False)
    RARIT_FAMILIAR = 'familiar'
    RARIT_REGULAR = 'regular'
    RARIT_EXCEPTIONAL = 'exceptional'
    RARIT_CHOICES = [
        (RARIT_FAMILIAR, 'Familiar'),
        (RARIT_REGULAR, 'Regular'),
        (RARIT_EXCEPTIONAL, 'Exceptional'),
    ]
    # Relative abundance tiers allowed when picking species (CountrySpecies.frequency).
    RARIT_FREQUENCY_TIERS = {
        RARIT_FAMILIAR: (
            'abundant',
            'very_common',
            'common',
        ),
        RARIT_REGULAR: (
            'abundant',
            'very_common',
            'common',
            'fairly_common',
            'uncommon',
            'rare',
        ),
        RARIT_EXCEPTIONAL: (
            'abundant',
            'very_common',
            'common',
            'fairly_common',
            'uncommon',
            'rare',
            'very_rare',
            'vagrant',
        ),
    }
    rarity = models.CharField(
        max_length=20,
        default=RARIT_REGULAR,
        choices=RARIT_CHOICES,
        help_text='Filter CountrySpecies by frequency tier for question selection.',
    )
    include_escapes = models.BooleanField(default=False)
    dificult_species = models.BooleanField(
        default=False,
        help_text='Pick question species randomly from the top 100 most often answered wrong '
        'for this country (global mistake stats).',
    )
    GAME_TYPE_STANDARD = 'standard'
    GAME_TYPE_EXTREME = 'extreme'
    GAME_TYPE_PAIR_PRACTICE = 'pair_practice'
    GAME_TYPE_SPECIES_PRACTICE = 'species_practice'
    GAME_TYPE_FLOCK_CHALLENGE = 'flock_challenge'
    GAME_TYPE_CHOICES = [
        (GAME_TYPE_STANDARD, 'Standard'),
        (GAME_TYPE_EXTREME, 'Extreme'),
        (GAME_TYPE_PAIR_PRACTICE, 'Pair practice'),
        (GAME_TYPE_SPECIES_PRACTICE, 'Species practice'),
        (GAME_TYPE_FLOCK_CHALLENGE, 'Flock challenge'),
    ]
    game_type = models.CharField(
        max_length=20,
        default=GAME_TYPE_STANDARD,
        choices=GAME_TYPE_CHOICES,
        help_text='Extreme: favor rare species and species this player has missed before.',
    )
    questions_pregenerated = models.BooleanField(
        default=False,
        help_text='When True, all questions (and locked media) exist before play; '
        'add_question only advances to the next pre-created row.',
    )
    pair_species_low = models.ForeignKey(
        'jizz.Species',
        null=True,
        blank=True,
        related_name='pair_practice_games_low',
        on_delete=models.SET_NULL,
    )
    pair_species_high = models.ForeignKey(
        'jizz.Species',
        null=True,
        blank=True,
        related_name='pair_practice_games_high',
        on_delete=models.SET_NULL,
    )
    focus_species = models.ForeignKey(
        'jizz.Species',
        null=True,
        blank=True,
        related_name='species_practice_games',
        on_delete=models.SET_NULL,
        help_text='Target species for species_practice games.',
    )
    speed_seconds = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='When set, the player must answer within this many seconds or the round counts as wrong.',
    )
    host = models.ForeignKey('jizz.Player', null=True, related_name='host', on_delete=models.CASCADE)
    force_ended = models.BooleanField(
        default=False,
        help_text='True when a player ended the session early (WebSocket end_game) before all rounds.',
    )

    tax_family = models.CharField(
        'Taxonomic family',
        help_text='Only show birds from this family',
        max_length=100,
        choices=lazy(get_tax_family_choices, tuple)(),
        null=True,
        blank=True
    )

    tax_order = models.CharField(
        'Taxonomic order',
        help_text='Only show birds from this order',
        max_length=100,
        choices=lazy(get_tax_order_choices, tuple)(),
        null=True,
        blank=True
    )

    species_group = models.CharField(
        'Species group',
        help_text='Only show birds from this group (e.g. shorebirds, warblers)',
        max_length=80,
        choices=lazy(get_species_group_choices, tuple)(),
        null=True,
        blank=True,
    )

    SEASON_SPRING = 'spring'
    SEASON_SUMMER = 'summer'
    SEASON_AUTUMN = 'autumn'
    SEASON_WINTER = 'winter'
    SEASON_CHOICES = [
        (SEASON_SPRING, 'Spring'),
        (SEASON_SUMMER, 'Summer'),
        (SEASON_AUTUMN, 'Autumn'),
        (SEASON_WINTER, 'Winter'),
    ]
    season = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=SEASON_CHOICES,
        help_text='When set, question selection uses monthly eBird frequency for this season.',
    )

    @classmethod
    def frequency_filter_q(cls, rarity=None) -> Q:
        """Q filter for species linked to the game country with allowed frequency tiers."""
        tier = rarity or cls.RARIT_REGULAR
        freqs = cls.RARIT_FREQUENCY_TIERS.get(tier, cls.RARIT_FREQUENCY_TIERS[cls.RARIT_REGULAR])
        q = Q(countryspecies__frequency__in=freqs)
        if tier in (cls.RARIT_REGULAR, cls.RARIT_EXCEPTIONAL):
            q |= Q(countryspecies__frequency__isnull=True) | Q(countryspecies__frequency='')
        return q

    @classmethod
    def country_species_rarity_q(cls, rarity=None) -> Q:
        """Same tier rules as ``frequency_filter_q`` on ``CountrySpecies`` rows."""
        tier = rarity or cls.RARIT_REGULAR
        freqs = cls.RARIT_FREQUENCY_TIERS.get(tier, cls.RARIT_FREQUENCY_TIERS[cls.RARIT_REGULAR])
        q = Q(frequency__in=freqs)
        if tier in (cls.RARIT_REGULAR, cls.RARIT_EXCEPTIONAL):
            q |= Q(frequency__isnull=True) | Q(frequency='')
        return q

    @property
    def current_highscore(self):
        return PlayerScore.highscore_by_type(
            level=self.level,
            country=self.country,
            length=self.length,
            media=self.media,
            rarity=self.rarity,
            season=self.season,
        )

    @property
    def ended(self):
        if self.force_ended:
            return True
        return self.questions.filter(done=True).count() >= self.length

    @property
    def last_question(self):
        return self.questions.last()

    def can_accept_start_game(self) -> bool:
        """
        Whether WebSocket start_game should activate/broadcast the first round.

        Pregenerated games already have questions; allow start while Q1 is still
        the active round. Lazy games only accept start when no questions exist yet.
        """
        if self.questions_pregenerated or self.game_type == self.GAME_TYPE_FLOCK_CHALLENGE:
            current = self.questions.filter(done=False).order_by('sequence').first()
            if current is None:
                return False
            if current.sequence != 1 or self.questions.filter(done=True).exists():
                return False
            return True
        return not self.questions.exists()

    def add_question(self):
        """
        Generate a new question for this game.

        If there is already an active (undone) round that is not finished yet
        (no host answer — see ``can_advance_to_next_question``), returns that
        question and does not create another. This makes duplicate WebSocket/API
        calls idempotent and prevents skipped rounds.

        Process when advancing:
        1. Mark all previous undone questions as done
        2. Select random species based on game filters
        3. Select random media item for the species
        4. Generate answer options based on game level
        5. Create Question and QuestionOption instances

        For ``questions_pregenerated`` games, steps 2–5 are skipped: the next
        pre-created Question row is returned instead.

        Returns:
            Question instance or None if game has ended

        Note: Questions are generated lazily (on-demand) rather than
        all at once. This allows for dynamic game progression.

        See docs/GAME_LIFECYCLE.md for detailed documentation.

        Concurrent callers (e.g. many HTTP GETs on /api/games/<token>/question/ when
        ``game_started`` is broadcast) must serialize on this game row or each request
        can observe no active question and create duplicate rounds (sequence jumps).
        """
        with transaction.atomic():
            # Lock only jizz_game — select_related + FOR UPDATE breaks PostgreSQL
            # ("nullable side of an outer join") when FKs like country are nullable.
            game = Game.objects.select_for_update(of=("self",)).get(pk=self.pk)
            current = game.questions.filter(done=False).order_by('sequence').first()
            if current is not None and not game.can_advance_to_next_question(current):
                return current

            if game.questions_pregenerated or game.game_type == Game.GAME_TYPE_FLOCK_CHALLENGE:
                if current is not None:
                    current.done = True
                    current.save(update_fields=['done'])
                nxt = game.questions.filter(done=False).order_by('sequence').first()
                return nxt

            game.questions.filter(done=False).update(done=True)
            return Game._add_question_body(game)

    @staticmethod
    def _add_question_body(game):
        """Create the next question row; caller must hold ``game`` locked in ``add_question``."""
        from jizz.game_question_selection import create_question_for_game

        return create_question_for_game(game)

    @property
    def question(self):
        """
        Get the current active (undone) question.

        Returns the first question where done=False, ordered by sequence,
        ensuring players always get the current question, not a completed one.

        Returns:
            Question instance or None if no active question exists
        """
        return self.questions.filter(done=False).order_by('sequence').first()

    def can_advance_to_next_question(self, current=None):
        """
        True when the current round may be closed and a new one created.

        Requires an answer from the game host on the current question so duplicate
        ``next_question`` / ``start_game`` WebSocket actions cannot skip rounds.
        If ``host`` is unset, any answer on the current question suffices.
        """
        current = current if current is not None else self.question
        if current is None:
            return False
        host = self.host
        if host is None:
            return current.answers.exists()
        return current.answers.filter(player_score__player_id=host.id).exists()

    @property
    def progress(self):
        return self.questions.count()

    def __str__(self):
        return f'{self.country} - {self.level} - {self.created.strftime("%X %x")}'


class CountryBadges(models.Model):
    player = models.ForeignKey('jizz.Player', on_delete=models.CASCADE)
    country = models.ForeignKey('jizz.Country', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)


def generate_player_token():
    return str(uuid.uuid4())


class Player(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey('auth.User', blank=True, null=True, on_delete=models.CASCADE)
    ip = models.GenericIPAddressField(null=True, blank=True)
    name = models.CharField(max_length=255)
    language = models.CharField(max_length=100, default='en')
    token = models.CharField(max_length=100, default=generate_player_token, editable=False)
    score = models.IntegerField(default=0)

    @property
    def games(self):
        return self.scores.count()

    @property
    def country_badges(self):
        return self.scores.filter(
            game__length=20,
            score__gte=6000,
            game__level='advanced'
        ).order_by('score').distinct('game__country')

    @property
    def play_time(self):
        return sum([score.play_time for score in self.scores.all()], timedelta())

    @property
    def playtime(self):
        seconds = self.play_time.total_seconds()
        hours = round(seconds // 3600)
        minutes = round((seconds % 3600) // 60)
        if hours == 0:
            return f'{minutes} minutes'
        return f'{hours} hours and {minutes} minutes'

    def __str__(self):
        return f"{self.name} - #{self.id}"


class UserProfile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    receive_updates = models.BooleanField(default=True, help_text='Receive Birdr news and update emails')
    language = models.CharField(max_length=10, default='en', blank=True, help_text='Bird name language')
    app_language = models.CharField(
        max_length=10,
        default='',
        blank=True,
        help_text='App UI language (empty = not set; clients guess from the device)',
    )
    country = models.ForeignKey('jizz.Country', on_delete=models.SET_NULL, null=True, blank=True, help_text='Preferred country')
    timezone = models.CharField(
        max_length=63,
        default='Europe/Amsterdam',
        blank=True,
        help_text='Timezone for daily challenge (e.g. Europe/Amsterdam)',
    )
    VISUAL_STYLE_CLASSIC = 'classic'
    VISUAL_STYLE_STYLISH = 'stylish'
    VISUAL_STYLE_NONE = 'none'
    VISUAL_STYLE_CHOICES = [
        (VISUAL_STYLE_CLASSIC, 'Classic'),
        (VISUAL_STYLE_STYLISH, 'Stylish'),
        (VISUAL_STYLE_NONE, 'None'),
    ]
    visual_style = models.CharField(
        max_length=16,
        choices=VISUAL_STYLE_CHOICES,
        default=VISUAL_STYLE_CLASSIC,
        help_text='In-app illustration style (classic comic, stylish, or none)',
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"


class PlayerScore(models.Model):
    DEVICE_IOS = 'ios'
    DEVICE_ANDROID = 'android'
    DEVICE_WEB = 'web'
    DEVICE_TYPE_CHOICES = [
        (DEVICE_IOS, 'iOS'),
        (DEVICE_ANDROID, 'Android'),
        (DEVICE_WEB, 'Web'),
    ]

    player = models.ForeignKey(Player, related_name='scores', on_delete=models.CASCADE)
    game = models.ForeignKey(Game, related_name='scores', blank=True, null=True, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    app_version = models.CharField(max_length=32, blank=True, default='')
    device_type = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=DEVICE_TYPE_CHOICES,
    )

    @property
    def play_time(self):
        if not self.answers.exists():
            return timedelta()
        return self.answers.last().created - self.game.created

    @property
    def playtime(self):
        seconds = self.play_time.total_seconds()
        hours = round(seconds // 3600)
        minutes = round((seconds % 3600) // 60)
        if hours == 0:
            return f'{minutes} minutes'
        return f'{hours} hours and {minutes} minutes'

    @classmethod
    def highscore_by_type(
        cls, level=None, country=None, media=None, length=None, rarity=None, season=None
    ):
        qs = cls.objects.filter(
            game__level=level,
            game__country=country,
            game__media=media,
            game__length=length,
        )
        if rarity is not None:
            qs = qs.filter(game__rarity=rarity)
        if season:
            qs = qs.filter(game__season=season)
        else:
            qs = qs.filter(Q(game__season='') | Q(game__season__isnull=True))
        return qs.order_by('-score').first()

    @property
    def ranking(self):
        scores = PlayerScore.objects.filter(
            game__level=self.game.level,
            game__country=self.game.country,
            game__media=self.game.media,
            game__length=self.game.length,
            game__rarity=self.game.rarity,
        )
        if self.game.season:
            scores = scores.filter(game__season=self.game.season)
        else:
            scores = scores.filter(Q(game__season='') | Q(game__season__isnull=True))
        scores = scores.order_by('-score').all()
        return list(scores).index(self) + 1

    @property
    def is_host(self):
        return self.game_id and self.game.host == self

    @property
    def status(self):
        question = self.game_id and self.game.questions.last()
        if not question:
            return 'waiting'
        answer = self.answers.filter(question=question).first()
        if answer:
            if answer.correct:
                return 'correct'
            else:
                return 'incorrect'
        return 'waiting'

    @property
    def last_answer(self):
        """Answer on the current (last) question, or None if still waiting."""
        question = self.game_id and self.game.questions.last()
        if not question:
            return None
        return self.answers.filter(question=question).first()

    class Meta:
        unique_together = ('player', 'game')


class Answer(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    question = models.ForeignKey('jizz.Question', related_name='answers', on_delete=models.CASCADE)
    player_score = models.ForeignKey('jizz.PlayerScore', null=True, related_name='answers', on_delete=models.CASCADE)
    answer = models.ForeignKey('jizz.Species', related_name='answer', on_delete=models.CASCADE)
    correct = models.BooleanField(default=False)
    score = models.IntegerField(default=0)

    def calculate_score(self):
        start = self.question.created
        ready = QuestionMediaReady.objects.filter(
            question=self.question,
            player=self.player_score.player,
        ).first()
        if ready and ready.ready_at:
            start = max(start, ready.ready_at)
        time_taken = (now() - start).total_seconds()
        time_taken = max(0.0, time_taken)
        max_score = 500
        min_score = 100
        score = min_score + (max_score - min_score) * math.exp(-time_taken / 10)
        return round(score)

    def save(self, *args, **kwargs):
        if not self.id:
            self.correct = self.answer == self.question.species
            if self.correct:
                self.score = self.calculate_score()
        return super().save(*args, **kwargs)

    class Meta:
        unique_together = ('player_score', 'question')


@receiver(post_save, sender=Answer)
def update_player_score(sender, instance, created, **kwargs):
    if created:
        instance.player_score.score = instance.player_score.answers.filter(
            question__game=instance.question.game
        ).aggregate(score=Sum('score'))['score']
        instance.player_score.save()


class SpeciesImage(models.Model):
    url = models.URLField()
    link = models.URLField(null=True, blank=True)
    contributor = models.CharField(max_length=200, null=True, blank=True)
    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name='old_images'
    )

    class Meta:
        unique_together = ('species', 'url')



class SpeciesSound(models.Model):
    url = models.URLField()
    link = models.URLField(null=True, blank=True)
    contributor = models.CharField(max_length=200, null=True, blank=True)
    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name='old_sounds'
    )

    class Meta:
        unique_together = ('species', 'url')


class SpeciesVideo(models.Model):
    url = models.URLField()
    link = models.URLField(null=True, blank=True)
    contributor = models.CharField(max_length=200, null=True, blank=True)
    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name='old_videos'
    )

    class Meta:
        unique_together = ('species', 'url')


class FlagQuestion(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='flags',
        null=True,
        blank=True
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='flags'
    )
    media_url = models.URLField(null=True, blank=True)
    description = models.CharField(max_length=200, null=True, blank=True)
    created = models.DateTimeField(auto_now=True)
    

class CountrySpecies(models.Model):
    country = models.ForeignKey(
        Country,
        related_name='countryspecies',
        on_delete=models.CASCADE
    )
    species = models.ForeignKey(
        Species,
        related_name='countryspecies',
        on_delete=models.CASCADE
    )

    STATUS_CHOICES = [
        ('unknown', 'Unknown'),
        ('native', 'Native'),
        ('rare', 'Rare'),
        ('introduced', 'Introduced'),
        ('extirpated', 'Extirpated'),
        ('uncertain', 'Uncertain'),
        ('endemic', 'Endemic'),
    ]

    status = models.CharField(max_length=100, default='unknown', choices=STATUS_CHOICES)

    FREQUENCY_CHOICES = [
        ('abundant', 'Abundant'),
        ('very_common', 'Very common'),
        ('common', 'Common'),
        ('fairly_common', 'Fairly common'),
        ('uncommon', 'Uncommon'),
        ('rare', 'Rare'),
        ('very_rare', 'Very rare'),
        ('vagrant', 'Vagrant'),
    ]
    frequency = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=FREQUENCY_CHOICES,
        help_text='Relative abundance/frequency in this country (e.g. from eBird regional stats)',
    )

    frequency_pct = models.FloatField(
        null=True,
        blank=True,
        help_text='Raw percentage from source (e.g. range_occupied_percent from eBird Status and Trends CSV)',
    )

    @property
    def name(self):
        return self.species.name

    def __repr__(self):
        return self.species.name_latin

    def __str__(self):
        return self.species.name

    class Meta:
        verbose_name = 'Country Species'
        verbose_name_plural = 'Country Species'
        unique_together = ('country', 'species')


class CountrySpeciesFrequency(models.Model):
    """Per-month frequency from eBird (API, Status & Trends CSV, or future bulk CSV)."""

    CONFIDENCE_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    country_species = models.ForeignKey(
        CountrySpecies,
        on_delete=models.CASCADE,
        related_name='frequency_by_month',
    )
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    reference_year = models.PositiveSmallIntegerField(
        default=2020,
        help_text='Calendar year this month slice refers to (imports default to command --year).',
    )
    frequency_pct = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            'When from checklist-based eBird metrics: % of complete checklists in scope that '
            'report the species (0–100). Other sources: document in notes.'
        ),
    )
    frequency = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=CountrySpecies.FREQUENCY_CHOICES,
    )
    checklist_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Complete checklists in scope (denominator), when the source provides it.',
    )
    observation_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Raw observation or row count if available; never used alone for tiering.',
    )
    occupied_subregions = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Count of subregions / cells / locids where reported (meaning depends on source).',
    )
    occurrence_event_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Deduplicated occurrence estimate when the source provides it.',
    )
    source = models.CharField(
        max_length=64,
        default='ebird',
        blank=True,
        help_text='e.g. ebird_api_freqlist, ebird_st_pct_percentile',
    )
    source_updated_at = models.DateTimeField(null=True, blank=True)
    confidence = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=CONFIDENCE_CHOICES,
    )
    is_vagrant_like = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Country Species Frequency'
        verbose_name_plural = 'Country Species Frequencies'
        constraints = [
            models.UniqueConstraint(
                fields=('country_species', 'month', 'reference_year'),
                name='jizz_countryspeciesfrequency_unique_cs_month_year',
            ),
        ]
        ordering = ['country_species', 'reference_year', 'month']


class Feedback(models.Model):
    user = models.ForeignKey(
        'auth.User',
        related_name='feedback',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    player = models.ForeignKey(
        Player,
        related_name='feedback',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    comment = models.TextField(default='', null=True, blank=True)
    rating = models.IntegerField(default=0)
    contact_name = models.CharField(max_length=120, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)


class Update(models.Model):
    title_en = models.CharField(max_length=200)
    title_nl = models.CharField(max_length=200, blank=True, default='')
    body_en = QuillField()
    body_nl = QuillField(blank=True)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    published = models.BooleanField(default=True, help_text='Show in app and allow email sends')

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.title_en

    def title_for_language(self, language: str) -> str:
        from jizz.update_i18n import localized_title

        return localized_title(self, language)

    def body_for_language(self, language: str):
        from jizz.update_i18n import localized_body

        return localized_body(self, language)


class UpdateTranslation(models.Model):
    """Cached auto-translation of an update for an app UI language."""

    update = models.ForeignKey(Update, related_name='translations', on_delete=models.CASCADE)
    language = models.CharField(max_length=10)
    source_hash = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    body_html = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['update', 'language'], name='update_translation_lang_uniq'),
        ]
        indexes = [
            models.Index(fields=['update', 'language', 'source_hash']),
        ]

    def __str__(self):
        return f'{self.update_id} {self.language}'


class UpdateThumbsUp(models.Model):
    update = models.ForeignKey(Update, related_name='thumbs_ups', on_delete=models.CASCADE)
    user = models.ForeignKey(
        'auth.User',
        related_name='update_thumbs_ups',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    player = models.ForeignKey(
        Player,
        related_name='update_thumbs_ups',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(
                fields=['update', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_update_thumbs_up_user',
            ),
            models.UniqueConstraint(
                fields=['update', 'player'],
                condition=models.Q(player__isnull=False),
                name='unique_update_thumbs_up_player',
            ),
        ]


class MailSettings(models.Model):
    """Singleton email branding (logo, footer)."""

    logo = models.ImageField(upload_to='mail/', null=True, blank=True)
    footer_html_en = QuillField(blank=True)
    footer_html_nl = QuillField(blank=True)

    class Meta:
        verbose_name = 'Mail settings'
        verbose_name_plural = 'Mail settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Mail settings'


class UpdateEmailDelivery(models.Model):
    STATUS_SENDING = 'sending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SENDING, 'Sending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    update = models.ForeignKey(Update, related_name='email_deliveries', on_delete=models.CASCADE)
    sent_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='update_email_deliveries',
    )
    is_test = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    sent_at = models.DateTimeField(auto_now_add=True)
    recipient_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-sent_at']
        verbose_name_plural = 'Update email deliveries'

    def __str__(self):
        kind = 'test' if self.is_test else 'broadcast'
        return f'{kind} for update {self.update_id} ({self.recipient_count} recipients)'


class UpdateEmailRecipient(models.Model):
    delivery = models.ForeignKey(
        UpdateEmailDelivery,
        related_name='recipients',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='update_emails_received',
    )
    email = models.EmailField()
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']
        unique_together = ('delivery', 'user')

    def __str__(self):
        return f'{self.email} ({self.delivery_id})'


class Reaction(models.Model):
    player = models.ForeignKey(
        Player,
        related_name='reactions',
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    update = models.ForeignKey(
        Update,
        related_name='reactions',
        on_delete=models.CASCADE
    )
    message = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    @property
    def name(self):
        return self.player.name


# --- Birdr Journey ---


class JourneyLevel(models.Model):
    sequence = models.PositiveSmallIntegerField(unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(default='')
    title_nl = models.CharField(max_length=200, null=True, blank=True)
    description_nl = models.TextField(default='', null=True, blank=True)
    icon = models.ImageField(upload_to='journey_levels/')

    class Meta:
        ordering = ['sequence']

    def __str__(self):
        return f'Level {self.sequence}: {self.title}'

    @property
    def is_champion(self):
        return not self.steps.exists()


class JourneyStep(models.Model):
    STEP_TYPE_CHOICES = [
        ('plain', 'Plain'),
        ('sounds', 'Sounds'),
        ('family', 'Family'),
        ('difficult', 'Difficult'),
        ('extreme', 'Extreme'),
        ('speed', 'Speed'),
    ]

    journey_level = models.ForeignKey(
        JourneyLevel,
        related_name='steps',
        on_delete=models.CASCADE,
    )
    sequence = models.PositiveSmallIntegerField(default=0)
    step_type = models.CharField(
        max_length=32,
        choices=STEP_TYPE_CHOICES,
        default='plain',
    )
    level = models.CharField(
        max_length=20,
        choices=Game.LEVEL_CHOICES,
        default='advanced',
    )
    length = models.IntegerField(default=0)
    jokers = models.IntegerField(default=0)
    rarity = models.CharField(
        max_length=20,
        default=Game.RARIT_REGULAR,
        choices=Game.RARIT_CHOICES,
    )
    media = models.CharField(max_length=10, default='images', choices=Game.MEDIA_CHOICES)
    include_escapes = models.BooleanField(default=False)
    speed_seconds = models.PositiveSmallIntegerField(
        default=10,
        help_text='Seconds to answer each question (speed steps only).',
    )

    class Meta:
        ordering = ['journey_level', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['journey_level', 'sequence'],
                name='journey_step_unique_level_sequence',
            ),
        ]

    def __str__(self):
        return f'Level {self.journey_level.sequence} step {self.sequence}'


class BirdrJourney(models.Model):
    """Solo level progression per country for a user or guest player."""
    user = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='birdr_journeys',
    )
    player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='birdr_journeys',
    )
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='birdr_journeys',
    )
    current_sequence = models.PositiveSmallIntegerField(
        default=0,
        help_text='0-based index into JourneyLevel rows ordered by sequence',
    )
    current_step_sequence = models.PositiveSmallIntegerField(default=0)
    streak_days = models.PositiveIntegerField(default=0)
    last_played_date = models.DateField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, player__isnull=True)
                    | models.Q(user__isnull=True, player__isnull=False)
                ),
                name='birdr_journey_user_xor_player',
            ),
            models.UniqueConstraint(
                fields=['user', 'country'],
                condition=models.Q(user__isnull=False),
                name='birdr_journey_unique_user_country',
            ),
            models.UniqueConstraint(
                fields=['player', 'country'],
                condition=models.Q(player__isnull=False),
                name='birdr_journey_unique_player_country',
            ),
        ]

    def __str__(self):
        owner = self.user_id or f'player:{self.player_id}'
        return f'Journey {owner} @ {self.country_id} seq={self.current_sequence}'


class BirdrJourneyGame(models.Model):
    birdr_journey = models.ForeignKey(
        BirdrJourney,
        related_name='games',
        on_delete=models.CASCADE,
    )
    journey_step = models.ForeignKey(
        JourneyStep,
        related_name='journey_games',
        on_delete=models.CASCADE,
    )
    game = models.ForeignKey(
        Game,
        related_name='birdr_journey_games',
        on_delete=models.CASCADE,
    )
    created = models.DateTimeField(auto_now_add=True)

    @property
    def remaining_jokers(self):
        failed = self.game.questions.filter(
            answers__correct=False,
            answers__answer__isnull=False,
        ).count()
        return self.journey_step.jokers - failed

    @property
    def status(self):
        if self.remaining_jokers < 0:
            return 'failed'
        if self.game.ended and self.remaining_jokers >= 0:
            return 'passed'
        if self.game.questions.count():
            return 'running'
        return 'new'

    class Meta:
        ordering = ['-id']


# --- Daily Challenge & Friends ---


class Friendship(models.Model):
    """Friend request / friendship between two users. Symmetric once accepted."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]
    from_user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='friendship_sent'
    )
    to_user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='friendship_received'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')
        ordering = ['-created']


class DailyChallenge(models.Model):
    """A 7-day (or configurable) daily challenge series."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_accept', 'Pending accept'),
        ('active', 'Active'),
        ('ended', 'Ended'),
    ]
    creator = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='daily_challenges_created'
    )
    country = models.ForeignKey(
        'jizz.Country',
        on_delete=models.CASCADE,
        related_name='daily_challenges'
    )
    media = models.CharField(max_length=10, choices=Game.MEDIA_CHOICES, default='images')
    length = models.IntegerField(default=10)
    duration_days = models.IntegerField(default=7)
    level = models.CharField(max_length=20, default='advanced')
    started_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    token = ShortUUIDField(
        length=12,
        max_length=16,
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        unique=True,
        editable=False,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']


class DailyChallengeParticipant(models.Model):
    """User participating in a daily challenge (creator or invited)."""
    STATUS_CHOICES = [
        ('invited', 'Invited'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]
    challenge = models.ForeignKey(
        DailyChallenge,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='daily_challenge_participations'
    )
    invited_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='daily_challenge_invites_sent'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invited')
    accepted_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('challenge', 'user')
        ordering = ['-created']


class DailyChallengeInvite(models.Model):
    """Invite by email/phone for users not yet on Birdr (accept via link)."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
    ]
    challenge = models.ForeignKey(
        DailyChallenge,
        on_delete=models.CASCADE,
        related_name='invites'
    )
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    invite_token = ShortUUIDField(
        length=16,
        max_length=24,
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        unique=True,
        editable=False,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.expires_at and self.pk is None:
            from django.utils.timezone import now
            self.expires_at = now() + timedelta(days=7)
        super().save(*args, **kwargs)


class DailyChallengeRound(models.Model):
    """One round = one day = one game in a daily challenge."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    challenge = models.ForeignKey(
        DailyChallenge,
        on_delete=models.CASCADE,
        related_name='rounds'
    )
    day_number = models.PositiveIntegerField()  # 1..duration_days
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='daily_challenge_rounds',
        null=True,
        blank=True
    )
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('challenge', 'day_number')
        ordering = ['challenge', 'day_number']


class DeviceToken(models.Model):
    """Push notification device token (FCM or Expo). Legacy; prefer PushDevice."""
    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
    ]
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='device_tokens'
    )
    token = models.CharField(max_length=500)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    created = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'token')
        ordering = ['-last_used']


class PushDevice(models.Model):
    """Expo push token for mobile app (one row per device token)."""

    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
    ]
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='push_devices',
    )
    expo_push_token = models.CharField(max_length=500, unique=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user_id} {self.platform} ({self.expo_push_token[:24]}…)'


class UsageEvent(models.Model):
    """First-party product analytics (page views and feature usage)."""

    EVENT_TYPE_CHOICES = [
        ('page_view', 'Page view'),
        ('feature', 'Feature'),
        ('api', 'API call'),
        ('websocket', 'WebSocket'),
    ]
    PLATFORM_CHOICES = [
        ('web', 'Web'),
        ('ios', 'iOS'),
        ('android', 'Android'),
    ]
    DEVICE_TYPE_CHOICES = [
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
        ('unknown', 'Unknown'),
    ]

    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='page_view')
    path = models.CharField(max_length=500)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='web')
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES, default='unknown')
    country_code = models.CharField(max_length=2, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_events',
    )
    session_key = models.CharField(max_length=64, blank=True, default='')
    user_agent = models.TextField(blank=True, default='')
    app_version = models.CharField(max_length=32, blank=True, default='')
    app_build = models.CharField(max_length=32, blank=True, default='')
    os_version = models.CharField(max_length=64, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['path', 'created_at']),
            models.Index(fields=['platform', 'created_at']),
            models.Index(fields=['country_code', 'created_at']),
            models.Index(fields=['app_version', 'created_at'], name='jizz_usagee_app_ver_idx'),
            models.Index(fields=['app_build', 'created_at'], name='jizz_usagee_app_bui_idx'),
        ]

    def __str__(self):
        return f'{self.platform} {self.path} @ {self.created_at:%Y-%m-%d %H:%M}'

    @property
    def proxy_headers(self) -> dict:
        meta = self.metadata or {}
        return meta.get('proxy') or meta.get('_request') or {}


class Flock(models.Model):
    """Persistent club/group of birders that runs standardized challenges."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=50, unique=True)
    owner = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='owned_flocks',
    )
    default_country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name='flocks',
    )
    is_private = models.BooleanField(
        default=True,
        help_text='Private flocks are only visible to members and invitees.',
    )
    logo = models.ImageField(upload_to='flock_logos/', null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def member_count(self) -> int:
        return self.memberships.count()

    def is_admin(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.owner_id == user.id:
            return True
        return self.memberships.filter(
            user=user, role__in=('owner', 'admin')
        ).exists()

    def is_member(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if self.owner_id == user.id:
            return True
        return self.memberships.filter(user=user).exists()


class FlockMembership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
    ]

    flock = models.ForeignKey(Flock, related_name='memberships', on_delete=models.CASCADE)
    user = models.ForeignKey(
        'auth.User',
        related_name='flock_memberships',
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('flock', 'user')]
        indexes = [models.Index(fields=['flock', 'role'])]

    def __str__(self):
        return f'{self.user_id}@{self.flock_id} ({self.role})'


class FlockInvite(models.Model):
    flock = models.ForeignKey(Flock, related_name='invites', on_delete=models.CASCADE)
    code = models.CharField(max_length=8, db_index=True)
    token = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='flock_invites_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['code'],
                condition=models.Q(is_active=True),
                name='flock_invite_active_code_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.code} ({"active" if self.is_active else "revoked"})'


class FlockChallenge(models.Model):
    PRESET_CLUB_MIX = 'club_mix'
    PRESET_CHOICES = [(PRESET_CLUB_MIX, 'Club Mix')]
    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ENDED = 'ended'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ENDED, 'Ended'),
    ]

    flock = models.ForeignKey(Flock, related_name='challenges', on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='flock_challenges')
    length = models.PositiveSmallIntegerField(default=20)
    preset = models.CharField(max_length=32, choices=PRESET_CHOICES, default=PRESET_CLUB_MIX)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='flock_challenges_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    public_token = models.CharField(max_length=16, unique=True, editable=False)

    class Meta:
        ordering = ['-starts_at']
        indexes = [
            models.Index(fields=['flock', 'status', '-starts_at']),
            models.Index(fields=['ends_at']),
        ]

    def __str__(self):
        return f'{self.title} ({self.flock_id})'

    @property
    def is_open(self) -> bool:
        now_ts = now()
        return (
            self.status == self.STATUS_ACTIVE
            and self.starts_at <= now_ts <= self.ends_at
        )


class FlockChallengeItem(models.Model):
    """Immutable snapshot row: same species/media/options for every participant."""

    challenge = models.ForeignKey(
        FlockChallenge, related_name='items', on_delete=models.CASCADE
    )
    sequence = models.PositiveSmallIntegerField()
    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    media = models.ForeignKey('media.Media', on_delete=models.PROTECT)
    media_type = models.CharField(max_length=16)
    level = models.CharField(max_length=32)
    rarity = models.CharField(max_length=32)
    option_species_ids = models.JSONField(default=list)

    class Meta:
        ordering = ['sequence']
        unique_together = [('challenge', 'sequence')]

    def __str__(self):
        return f'{self.challenge_id}#{self.sequence} species={self.species_id}'


class FlockChallengeAttempt(models.Model):
    challenge = models.ForeignKey(
        FlockChallenge, related_name='attempts', on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='flock_challenge_attempts',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='flock_challenge_attempts',
    )
    game = models.OneToOneField(
        Game,
        on_delete=models.CASCADE,
        related_name='flock_challenge_attempt',
    )
    is_ranked = models.BooleanField(default=False)
    is_practice = models.BooleanField(default=False)
    correct_count = models.PositiveSmallIntegerField(default=0)
    birdr_score = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    result_token = models.CharField(max_length=24, unique=True, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=['challenge', '-correct_count', '-birdr_score', 'completed_at']),
            models.Index(fields=['challenge', 'user']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['challenge', 'user'],
                condition=models.Q(is_ranked=True, completed_at__isnull=False),
                name='flock_one_ranked_completed_attempt',
            ),
        ]

    def __str__(self):
        kind = 'ranked' if self.is_ranked else 'practice'
        return f'{self.user_id} {kind} on {self.challenge_id}'


class FlockChallengeAttemptQuestion(models.Model):
    attempt = models.ForeignKey(
        FlockChallengeAttempt, related_name='question_links', on_delete=models.CASCADE
    )
    challenge_item = models.ForeignKey(FlockChallengeItem, on_delete=models.CASCADE)
    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name='flock_attempt_link'
    )

    class Meta:
        unique_together = [('attempt', 'challenge_item')]


class IpGeoCache(models.Model):
    """Persistent cache for IP → location lookups (staff analytics)."""

    ip_address = models.GenericIPAddressField(unique=True)
    country_code = models.CharField(max_length=2, blank=True, default='')
    country_name = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    is_private = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'IP geolocation cache'
        verbose_name_plural = 'IP geolocation cache'

    def __str__(self):
        if self.is_private:
            return f'{self.ip_address} (private/local)'
        label = self.country_code or self.country_name or 'unknown'
        return f'{self.ip_address} → {label}'

    def to_location_dict(self):
        if self.is_private:
            return {
                'country_code': '',
                'country_name': 'Private/local',
                'city': '',
            }
        return {
            'country_code': self.country_code,
            'country_name': self.country_name,
            'city': self.city,
        }

