from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from jizz.models import Country, CountrySpecies, Species, Game, Question, Answer, Player, QuestionOption, PlayerScore, QuestionMediaReady, FlagQuestion, \
    Feedback, Update, Reaction, Language, Page, SpeciesName, UserProfile, BirdrJourney, BirdrJourneyGame, \
    JourneyLevel, JourneyStep, TaxonomicOrder, TaxonomicFamily, SpeciesGroup, \
    Friendship, DailyChallenge, DailyChallengeParticipant, DailyChallengeInvite, DailyChallengeRound, DeviceToken
from media.models import Media, MediaReview, FlagMedia
from media.display_urls import media_display_url


def _species_name_for_language(species, language: str | None) -> str:
    """Common / translated name, or scientific name when language is `la`."""
    lang = (language or '').strip().lower().split('-')[0].split('_')[0]
    if lang == 'la':
        return species.name_latin or species.name
    prefetched = getattr(species, '_translated_names', None)
    if prefetched is not None:
        return prefetched[0].name if prefetched else species.name
    if language:
        try:
            return SpeciesName.objects.get(species=species, language_id=language).name
        except SpeciesName.DoesNotExist:
            pass
    return species.name


class CountrySerializer(serializers.ModelSerializer):
    parent = serializers.CharField(source='parent_id', read_only=True, allow_null=True)

    def to_internal_value(self, data):
        return Country.objects.get(code=data)

    class Meta:
        model = Country
        fields = ('code', 'name', 'count', 'parent', 'kind', 'hemisphere')



class QuestionMediaSerializer(serializers.ModelSerializer):
    link = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return media_display_url(obj.url)

    def get_link(self, obj):
        # Full source URLs can identify the species (e.g. iNaturalist observations).
        # Live play omits them; they are attached to the answer payload after guessing.
        if self.context.get('play_mode'):
            return None
        if not obj.link:
            return None
        try:
            parsed = urlparse(obj.link)
            return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else obj.link
        except Exception:
            return obj.link

    class Meta:
        model = Media
        fields = ('id', 'url', 'link', 'contributor', 'source')


class MediaSerializer(serializers.ModelSerializer):
    """Serializer for Media model (images, videos, audio). Optional review_status when level=thorough."""
    species_name = serializers.SerializerMethodField()
    species_code = serializers.CharField(source='species.code', read_only=True)
    species_id = serializers.IntegerField(source='species.id', read_only=True)
    review_status = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return media_display_url(obj.url)

    def get_species_name(self, obj):
        """Return species name in the requested language if available."""
        language = None
        request = self.context.get('request')
        if request:
            language = request.query_params.get('language')
        return _species_name_for_language(obj.species, language)

    def get_review_status(self, obj):
        """When level=thorough, return { approved, rejected, dont_know } counts for this media."""
        if self.context.get('level') != 'thorough':
            return None
        return {
            'approved': getattr(obj, '_approved_count', 0),
            'rejected': getattr(obj, '_rejected_count', 0),
            'dont_know': getattr(obj, '_not_sure_count', 0),
        }

    class Meta:
        model = Media
        fields = (
            'id', 'type', 'source', 'url', 'link', 'contributor', 'copyright_text',
            'copyright_standardized', 'non_commercial_only',
            'species_name', 'species_code', 'species_id', 'hide', 'created',
            'review_status',
        )


class SpeciesListSerializer(serializers.ModelSerializer):

    name_translated = serializers.SerializerMethodField()
    tax_order = serializers.CharField(read_only=True)
    tax_family = serializers.CharField(read_only=True)
    tax_family_en = serializers.CharField(read_only=True)

    def get_name_translated(self, obj):
        request = self.context.get('request')
        language = request.query_params.get('language') if request else None
        return _species_name_for_language(obj, language)

    class Meta:
        model = Species
        fields = ('name', 'name_latin', 'name_nl', 'name_translated', 'id', 'tax_family', 'tax_family_en', 'tax_order')


class SpeciesReviewStatsSerializer(serializers.Serializer):
    """Serializer for species with media review stats (annotated queryset)."""
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    total_media = serializers.IntegerField()
    unreviewed = serializers.SerializerMethodField()
    approved = serializers.IntegerField(source='approved_media')
    rejected = serializers.IntegerField(source='rejected_media')
    not_sure = serializers.IntegerField(source='not_sure_media')

    def get_name(self, obj):
        request = self.context.get('request')
        language = request and request.query_params.get('language')
        return _species_name_for_language(obj, language)

    def get_unreviewed(self, obj):
        return obj.total_media - obj.media_with_review


class MediaForReviewSerializer(MediaSerializer):
    """Media serializer with review_type for embedding in species (approved/rejected/not_sure or null)."""
    review_type = serializers.SerializerMethodField()
    machine_prediction = serializers.SerializerMethodField()
    machine_human_agreement = serializers.SerializerMethodField()

    def get_review_type(self, obj):
        reviews = list(obj.reviews.all())
        review = max(reviews, key=lambda r: r.id) if reviews else None
        return review.review_type if review else None

    def get_machine_prediction(self, obj):
        try:
            p = obj.first_assertion_prediction
        except ObjectDoesNotExist:
            return None
        return {
            'predicted_review_type': p.predicted_review_type,
            'confidence': p.confidence,
            'model_version': p.model_version,
            'features_version': p.features_version or None,
        }

    def get_machine_human_agreement(self, obj):
        eff = obj.effective_review_status
        try:
            p = obj.first_assertion_prediction
        except ObjectDoesNotExist:
            return None
        if eff is None:
            return None
        if p.predicted_review_type == eff:
            return 'agree'
        return 'disagree'

    class Meta(MediaSerializer.Meta):
        fields = MediaSerializer.Meta.fields + (
            'review_type',
            'machine_prediction',
            'machine_human_agreement',
        )


class SpeciesWithMediaReviewSerializer(serializers.Serializer):
    """Species with review stats and all media embedded for media-review page."""
    id = serializers.IntegerField(source='species.id')
    name = serializers.SerializerMethodField()
    total_media = serializers.IntegerField()
    unreviewed = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    not_sure = serializers.IntegerField()
    media = serializers.SerializerMethodField()

    def get_name(self, obj):
        request = self.context.get('request')
        language = request and request.query_params.get('language')
        return _species_name_for_language(obj['species'], language)

    def get_media(self, obj):
        return MediaForReviewSerializer(
            obj['media'], many=True, context=self.context
        ).data


class FamilyListSerializer(serializers.ModelSerializer):
    tax_family = serializers.CharField(source='name_latin', read_only=True)
    tax_family_en = serializers.CharField(source='name_en', read_only=True)
    count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TaxonomicFamily
        fields = ('tax_family', 'tax_family_en', 'count')


class OrderListSerializer(serializers.ModelSerializer):
    tax_order = serializers.CharField(source='name_latin', read_only=True)
    count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TaxonomicOrder
        fields = ('tax_order', 'count')


class SpeciesGroupListSerializer(serializers.ModelSerializer):
    species_group = serializers.CharField(source='slug', read_only=True)
    count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SpeciesGroup
        fields = (
            'species_group',
            'name_en',
            'name_nl',
            'name_es',
            'name_fr',
            'name_de',
            'name_it',
            'name_pt_br',
            'name_ja',
            'count',
        )


class SpeciesCoverSerializer(serializers.ModelSerializer):
    """Cover image for species UI (may trigger illustration generation)."""

    illustration_url = serializers.SerializerMethodField()
    illustration_status = serializers.SerializerMethodField()

    def get_illustration_url(self, obj):
        from jizz.services.species_cover import species_cover_url

        request = self.context.get('request')
        return species_cover_url(obj, request)

    def get_illustration_status(self, obj):
        from jizz.services.species_illustration import get_illustration_status

        return get_illustration_status(obj)

    class Meta:
        model = Species
        fields = ('id', 'illustration_url', 'illustration_status')


class SpeciesSlugSerializer(serializers.ModelSerializer):
    """Public lookup by slug for practice start pages."""

    name_translated = serializers.SerializerMethodField()

    def get_name_translated(self, obj):
        request = self.context.get('request') if isinstance(self.context, dict) else None
        language = None
        if request is not None:
            query_params = getattr(request, 'query_params', None)
            if query_params is not None:
                language = query_params.get('language')
            else:
                language = request.GET.get('language')
        return _species_name_for_language(obj, language)

    class Meta:
        model = Species
        fields = ('id', 'name', 'name_latin', 'name_nl', 'name_translated', 'slug')


class SpeciesDetailSerializer(serializers.ModelSerializer):
    images = QuestionMediaSerializer(many=True)
    videos = QuestionMediaSerializer(many=True)
    sounds = QuestionMediaSerializer(many=True)
    name_translated = serializers.SerializerMethodField()

    def get_name_translated(self, obj):
        """Get translated name based on game language or request language"""
        # Try to get language from game context first
        game = self.context.get('game') if isinstance(self.context, dict) else None
        language = None
        
        if game:
            language = game.language
        elif isinstance(self.context, dict) and 'request' in self.context:
            request = self.context['request']
            query_params = getattr(request, 'query_params', None)
            if query_params is not None:
                language = query_params.get('language')
            else:
                language = request.GET.get('language')

        return _species_name_for_language(obj, language)

    class Meta:
        model = Species
        fields = (
            'name', 'code', 'name_latin', 'name_nl', 'name_translated', 'id',
            'images', 'videos', 'sounds',
        )

class QuestionOptionPlaySerializer(serializers.ModelSerializer):
    """Multiple-choice option without loading all species media."""

    name_translated = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    videos = serializers.SerializerMethodField()
    sounds = serializers.SerializerMethodField()

    def get_images(self, obj):
        return []

    def get_videos(self, obj):
        return []

    def get_sounds(self, obj):
        return []

    def get_name_translated(self, obj):
        names = self.context.get('play_species_names') or {}
        lang = self.context.get('play_language')
        if lang and (obj.id, lang) in names:
            return names[(obj.id, lang)]
        return _species_name_for_language(obj, lang)

    class Meta:
        model = Species
        fields = (
            'id', 'code', 'name', 'name_latin', 'name_nl', 'name_translated',
            'images', 'videos', 'sounds',
        )


class QuestionPlaySerializer(serializers.ModelSerializer):
    """
    Live play payload: the current media item only (index 0). Serialized ``number``
    is always 0. Option species omit embedded media lists. Flagging uses next-media.

    ``media`` is the effective type for *this* question (``images`` / ``video`` / ``audio``).
    Prefer it over ``game.media`` for mixed-media games (e.g. flock Club Mix).
    """

    images = serializers.SerializerMethodField()
    videos = serializers.SerializerMethodField()
    sounds = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    game = serializers.SerializerMethodField()
    number = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()

    def _effective_game_media(self) -> str:
        play_type = self.context.get('play_media_type')
        if play_type == 'audio':
            return 'audio'
        if play_type == 'video':
            return 'video'
        if play_type == 'image':
            return 'images'
        game = self.context.get('game')
        if game is not None and getattr(game, 'media', None):
            return game.media
        return 'images'

    def _media_list_for_play(self, obj):
        from jizz.question_play import rotate_media_list_for_play

        by_species = self.context.get('play_media_by_species') or {}
        items = by_species.get(obj.species_id, [])
        if not items:
            return []
        rotated = rotate_media_list_for_play(items, obj.number or 0)
        return QuestionMediaSerializer(
            rotated[:1], many=True, context=self.context
        ).data

    def get_number(self, obj):
        # Active media is always at array index 0 after rotation.
        return 0

    def get_media(self, obj):
        return self._effective_game_media()

    def get_images(self, obj):
        if self.context.get('play_media_type') != 'image':
            return []
        return self._media_list_for_play(obj)

    def get_videos(self, obj):
        if self.context.get('play_media_type') != 'video':
            return []
        return self._media_list_for_play(obj)

    def get_sounds(self, obj):
        if self.context.get('play_media_type') != 'audio':
            return []
        return self._media_list_for_play(obj)

    def get_options(self, obj):
        opts = list(obj.options.all())
        return QuestionOptionPlaySerializer(
            [op.species for op in opts],
            many=True,
            context=self.context,
        ).data

    def get_game(self, obj):
        game = obj.game
        return {
            'token': game.token,
            'level': game.level,
            'media': self._effective_game_media(),
            'speed_seconds': game.speed_seconds,
        }

    class Meta:
        model = Question
        fields = (
            'id', 'done', 'options', 'images', 'videos', 'sounds',
            'number', 'sequence', 'game', 'media',
        )


class QuestionSerializer(serializers.ModelSerializer):
    images = QuestionMediaSerializer(source='species.images', many=True)
    videos = QuestionMediaSerializer(source='species.videos', many=True)
    sounds = QuestionMediaSerializer(source='species.sounds', many=True)
    options = serializers.SerializerMethodField()
    game = serializers.SerializerMethodField()

    def get_options(self, obj):
        option_orders = QuestionOption.objects.filter(question=obj).order_by('order')
        return SpeciesDetailSerializer(
            [op.species for op in option_orders],
            many=True,
            context={'game': obj.game, **self.context},
        ).data

    def get_game(self, obj):
        # Include game token so frontend can verify question belongs to current game
        return {'token': obj.game.token}

    class Meta:
        model = Question
        fields = ('id', 'done', 'options', 'images', 'videos', 'sounds', 'number', 'sequence', 'game')


def current_question_media(question):
    """Media item currently shown for this question in play."""
    locked = getattr(question, 'media', None)
    if locked is not None:
        return locked
    from jizz.question_play import (
        active_play_media,
        fetch_eligible_media_for_species,
    )

    game = getattr(question, 'game', None)
    media_type = 'image'
    if game is not None:
        media_type = {'images': 'image', 'video': 'video', 'audio': 'audio'}.get(
            game.media, 'image'
        )
    items = fetch_eligible_media_for_species(question.species_id, media_type)
    active = active_play_media(items, question.number or 0)
    return active[0] if active else None


class AnswerSerializer(serializers.ModelSerializer):
    player_token = serializers.CharField(write_only=True)
    correct = serializers.BooleanField(read_only=True)
    species = SpeciesDetailSerializer(source='question.species', read_only=True)
    species_frequency = serializers.SerializerMethodField()
    checklist_added = serializers.SerializerMethodField()
    checklist_missed = serializers.SerializerMethodField()
    media_link = serializers.SerializerMethodField()
    answer = SpeciesDetailSerializer(read_only=True)
    answer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    question_id = serializers.IntegerField(write_only=True)
    timed_out = serializers.BooleanField(write_only=True, required=False, default=False)
    number = serializers.IntegerField(read_only=True, source='question.number')
    sequence = serializers.IntegerField(source='question.sequence', read_only=True)

    def get_species_frequency(self, obj):
        if not hasattr(obj, 'question'):
            return None
        game = self.context.get('game') or obj.question.game
        if not game or not game.country_id:
            return None
        from jizz.species_frequency import species_frequency_for_game

        return species_frequency_for_game(game, obj.question.species_id)

    def get_checklist_added(self, obj):
        return bool(getattr(obj, 'checklist_added', False))

    def get_checklist_missed(self, obj):
        return bool(getattr(obj, 'checklist_missed', False))

    def get_media_link(self, obj):
        """Full source URL for the played media. Only on the answering player's payload."""
        if not self.context.get('include_media_link'):
            return None
        question = getattr(obj, 'question', None)
        if question is None:
            return None
        media = current_question_media(question)
        return media.link if media and media.link else None

    def validate(self, attrs):
        timed_out = attrs.get('timed_out', False)
        if not timed_out and not attrs.get('answer_id'):
            raise serializers.ValidationError(
                {'answer_id': 'This field is required unless timed_out is true.'}
            )
        return attrs

    def create(self, validated_data):
        player = Player.objects.select_related('user').get(
            token=validated_data.pop('player_token')
        )
        question = Question.objects.select_related('game__country', 'media').get(
            id=validated_data.pop('question_id')
        )
        timed_out = validated_data.pop('timed_out', False)
        if timed_out:
            wrong_option = (
                QuestionOption.objects.filter(question=question)
                .exclude(species_id=question.species_id)
                .select_related('species')
                .first()
            )
            if not wrong_option:
                raise serializers.ValidationError(
                    {'timed_out': 'No incorrect option available for this question.'}
                )
            answer = wrong_option.species
            correct = False
        else:
            answer = Species.objects.get(id=validated_data.pop('answer_id'))
            correct = answer == question.species
        player_score, _created = PlayerScore.objects.get_or_create(player=player, game=question.game)
        request = self.context.get('request')
        if request is not None:
            from jizz.client_info import client_info_from_request, apply_player_score_client

            apply_player_score_client(player_score, *client_info_from_request(request))
        if Answer.objects.filter(player_score=player_score, question=question).exists():
            existing = Answer.objects.filter(player_score=player_score, question=question).first()
            existing.checklist_added = False
            existing.checklist_missed = False
            return existing
        from jizz.services.checklist import compute_checklist_added, compute_checklist_missed

        checklist_added = compute_checklist_added(
            player, question, correct, request=request
        )
        checklist_missed = compute_checklist_missed(
            player, question, correct, request=request
        )
        row = Answer.objects.create(
            player_score=player_score, question=question, answer=answer, correct=correct
        )
        row.checklist_added = checklist_added
        row.checklist_missed = checklist_missed
        return row

    class Meta:
        model = Answer
        fields = (
            'id', 'question_id', 'player_token',
            'answer', 'correct', 'species', 'species_frequency', 'checklist_added', 'checklist_missed',
            'media_link',
            'answer_id', 'timed_out', 'number', 'score',
            'sequence',
        )
        unique_together = ('question', 'player')


class FlagQuestionSerializer(serializers.ModelSerializer):

    player_token = serializers.CharField(write_only=True)
    question_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    media_url = serializers.URLField(write_only=True, required=False, allow_null=True)
    media_type = serializers.CharField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = FlagQuestion
        fields = ('player_token', 'description', 'question_id', 'media_url', 'media_type')

    def create(self, validated_data):
        player = Player.objects.get(token=validated_data.pop('player_token'))
        question_id = validated_data.pop('question_id', None)
        media_url = validated_data.pop('media_url', None)
        description = validated_data.pop('description', '')
        media_type = validated_data.pop('media_type', None)
        
        # If question_id is provided, use it; otherwise create with null question
        if question_id:
            question = Question.objects.get(id=question_id)
            return FlagQuestion.objects.create(
                description=description, 
                player=player, 
                question=question,
                media_url=media_url
            )
        else:
            # For media-only flags, create with null question
            if not media_url:
                raise serializers.ValidationError("Either question_id or media_url must be provided")
            return FlagQuestion.objects.create(
                description=description,
                player=player,
                question=None,
                media_url=media_url
            )


def upsert_media_review(media, review_type, description, user, player):
    """Create or update the single MediaReview for this media and reviewer (exactly one of user or player)."""
    if player:
        review, created = MediaReview.objects.get_or_create(
            media=media,
            player=player,
            defaults={'review_type': review_type, 'description': description},
        )
    else:
        review, created = MediaReview.objects.get_or_create(
            media=media,
            user=user,
            defaults={'review_type': review_type, 'description': description},
        )
    if not created:
        review.review_type = review_type
        review.description = description
        review.save()
    return review


def _validate_reviewer_player_token(data, request):
    if request and request.user and request.user.is_authenticated:
        if data.get('player_token'):
            raise serializers.ValidationError(
                {'player_token': 'Do not send player_token when authenticated as a user.'}
            )
        return
    if not data.get('player_token'):
        raise serializers.ValidationError(
            {'player_token': 'Either authenticate as a user or provide player_token.'}
        )


class ReviewMediaSerializer(serializers.ModelSerializer):
    """Serializer for reviewing media items (positive or negative). Accepts player_token or uses request.user if authenticated."""
    player_token = serializers.CharField(write_only=True, required=False)
    media_id = serializers.IntegerField(write_only=True)
    review_type = serializers.ChoiceField(choices=MediaReview.REVIEW_CHOICES, write_only=True)

    class Meta:
        model = MediaReview
        fields = ('player_token', 'description', 'media_id', 'review_type')

    def validate(self, data):
        request = self.context.get('request')
        _validate_reviewer_player_token(data, request)
        return data

    def create(self, validated_data):
        media = Media.objects.get(id=validated_data.pop('media_id'))
        review_type = validated_data.pop('review_type')
        description = validated_data.pop('description', '')
        request = self.context.get('request')
        player = None
        user = None

        if request and request.user and request.user.is_authenticated:
            user = request.user
        else:
            player = Player.objects.get(token=validated_data.pop('player_token'))

        return upsert_media_review(media, review_type, description, user, player)


FIRST_ASSERTION_REVIEW_CHOICES = (
    (MediaReview.APPROVED, 'Approved'),
    (MediaReview.REJECTED, 'Rejected'),
)


class FirstAssertionReviewSerializer(serializers.Serializer):
    """Image-only first assertion: approved or rejected only (no not_sure)."""
    player_token = serializers.CharField(required=False, allow_blank=True)
    media_id = serializers.IntegerField()
    review_type = serializers.ChoiceField(choices=FIRST_ASSERTION_REVIEW_CHOICES)
    description = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        request = self.context.get('request')
        _validate_reviewer_player_token(data, request)
        return data

    def validate_media_id(self, value):
        try:
            media = Media.objects.get(pk=value)
        except Media.DoesNotExist as exc:
            raise serializers.ValidationError('Invalid media id.') from exc
        if media.type != 'image':
            raise serializers.ValidationError(
                'First assertion reviews are only allowed for image media.'
            )
        return value

    def create(self, validated_data):
        media = Media.objects.get(pk=validated_data.pop('media_id'))
        review_type = validated_data.pop('review_type')
        description = validated_data.pop('description', '') or ''
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data.pop('player_token', None)
            user = request.user
            player = None
        else:
            player = Player.objects.get(token=validated_data.pop('player_token'))
            user = None
        return upsert_media_review(media, review_type, description, user, player)


class MediaReviewBriefSerializer(serializers.ModelSerializer):
    """201 response body for review create endpoints."""

    class Meta:
        model = MediaReview
        fields = ('id', 'review_type', 'description', 'created', 'media')
        read_only_fields = fields


class FlagMediaSerializer(serializers.ModelSerializer):
    """Serializer for flagging media items."""
    player_token = serializers.CharField(write_only=True)
    media_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = FlagMedia
        fields = ('player_token', 'description', 'media_id')

    def create(self, validated_data):
        player = Player.objects.get(token=validated_data.pop('player_token'))
        media = Media.objects.get(id=validated_data.pop('media_id'))
        description = validated_data.pop('description', '')
        # Use get_or_create to handle unique_together constraint
        flag, created = FlagMedia.objects.get_or_create(
            media=media,
            player=player,
            defaults={'description': description}
        )
        if not created:
            # Update existing flag
            flag.description = description
            flag.save()
        return flag


class ReactionSerializer(serializers.ModelSerializer):

    player_token = serializers.CharField(write_only=True)
    update_id = serializers.IntegerField(write_only=True)
    name = serializers.CharField(read_only=True)

    class Meta:
        model = Reaction
        fields = ('player_token', 'message', 'update_id', 'created', 'name')

    def create(self, validated_data):
        player = Player.objects.get(token=validated_data.pop('player_token'))
        update = Update.objects.get(id=validated_data.pop('update_id'))
        message = validated_data.pop('message')
        return Reaction.objects.create(message=message, player=player, update=update)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    is_staff = serializers.BooleanField(source='user.is_staff', read_only=True)
    is_superuser = serializers.BooleanField(source='user.is_superuser', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    country_code = serializers.CharField(source='country.code', read_only=True, allow_null=True)
    country_name = serializers.CharField(source='country.name', read_only=True, allow_null=True)

    class Meta:
        model = UserProfile
        fields = ('username', 'email', 'first_name', 'last_name', 'avatar', 'avatar_url', 'receive_updates', 'language', 'app_language', 'timezone', 'visual_style', 'country_code', 'country_name', 'is_staff', 'is_superuser')
        read_only_fields = ('avatar_url', 'country_code', 'country_name', 'is_staff', 'is_superuser')

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                url = request.build_absolute_uri(obj.avatar.url)
                # In production (behind proxy), ensure HTTPS so avatars load over HTTPS
                from django.conf import settings
                if not getattr(settings, 'DEBUG', True) and url.startswith('http://'):
                    url = 'https://' + url[7:]
                return url
            return obj.avatar.url
        return None

    def update(self, instance, validated_data):
        # Update avatar if provided
        if 'avatar' in validated_data:
            instance.avatar = validated_data['avatar']
        instance.save()
        return instance


class UserProfileUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, max_length=150, allow_blank=False)
    first_name = serializers.CharField(required=False, max_length=150, allow_blank=True)
    last_name = serializers.CharField(required=False, max_length=150, allow_blank=True)
    avatar = serializers.ImageField(required=False, allow_null=True)
    receive_updates = serializers.BooleanField(required=False)
    language = serializers.CharField(required=False, max_length=10, allow_blank=True)
    app_language = serializers.CharField(required=False, max_length=10, allow_blank=True)
    timezone = serializers.CharField(required=False, max_length=63, allow_blank=True)
    visual_style = serializers.ChoiceField(
        required=False,
        choices=('classic', 'stylish', 'none'),
    )
    country_code = serializers.CharField(required=False, max_length=10, allow_blank=True, allow_null=True)

    def validate_username(self, value):
        if value:
            from jizz.user_names import make_unique_username, sanitize_username

            value = sanitize_username(value.strip())
            user = self.context['request'].user
            return make_unique_username(value, exclude_user_id=user.pk)
        return value

    def validate_app_language(self, value):
        from jizz.app_languages import APP_LANGUAGES, normalize_app_language

        normalized = normalize_app_language(value)
        if (value or '').strip() and normalized not in APP_LANGUAGES:
            raise serializers.ValidationError("Invalid app language.")
        return normalized

    def validate_country_code(self, value):
        if value:
            try:
                Country.objects.get(code=value)
            except Country.DoesNotExist:
                raise serializers.ValidationError("Invalid country code.")
        return value

    def validate_avatar(self, value):
        if value:
            from django.core.exceptions import ValidationError as DjangoValidationError
            from jizz.avatar import resize_avatar_upload

            try:
                return resize_avatar_upload(value)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(
                    exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
                )
        return value

    def update(self, instance, validated_data):
        # Update username if provided
        if 'username' in validated_data and validated_data['username']:
            instance.user.username = validated_data['username']
        
        # Update first_name if provided
        if 'first_name' in validated_data:
            instance.user.first_name = validated_data['first_name']
        
        # Update last_name if provided
        if 'last_name' in validated_data:
            instance.user.last_name = validated_data['last_name']
        
        # Save user if any user fields were updated
        if 'username' in validated_data or 'first_name' in validated_data or 'last_name' in validated_data:
            instance.user.save()
        
        # Update avatar if provided
        if 'avatar' in validated_data:
            if validated_data['avatar'] is None:
                # Remove avatar
                if instance.avatar:
                    instance.avatar.delete()
                instance.avatar = None
            else:
                # Update avatar
                if instance.avatar:
                    instance.avatar.delete()
                instance.avatar = validated_data['avatar']
        
        # Update receive_updates if provided
        if 'receive_updates' in validated_data:
            instance.receive_updates = validated_data['receive_updates']
        
        if 'app_language' in validated_data:
            instance.app_language = validated_data['app_language']

        if 'language' in validated_data:
            instance.language = validated_data['language']
        elif 'app_language' in validated_data and validated_data['app_language']:
            from jizz.app_languages import species_language_from_app_language

            instance.language = species_language_from_app_language(
                validated_data['app_language']
            )
        
        # Update timezone if provided
        if 'timezone' in validated_data:
            instance.timezone = (validated_data['timezone'] or 'Europe/Amsterdam').strip() or 'Europe/Amsterdam'

        if 'visual_style' in validated_data:
            instance.visual_style = validated_data['visual_style']
        
        # Update country if provided
        if 'country_code' in validated_data:
            country_code = validated_data['country_code']
            if country_code:
                try:
                    instance.country = Country.objects.get(code=country_code)
                except Country.DoesNotExist:
                    pass
            else:
                instance.country = None
        
        instance.save()
        return instance


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def validate_username(self, value):
        from jizz.user_names import make_unique_username, sanitize_username

        value = sanitize_username(value.strip())
        if not value:
            raise serializers.ValidationError("Username is required.")
        return make_unique_username(value)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    uid = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)


class UpdateSerializer(serializers.ModelSerializer):
    """Legacy serializer kept for admin compatibility."""

    reactions = ReactionSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    title = serializers.CharField(source='title_en', read_only=True)
    message = serializers.SerializerMethodField()

    class Meta:
        model = Update
        fields = ('id', 'created', 'user', 'title', 'message', 'reactions', 'user')

    def get_message(self, obj):
        from jizz.update_emails import quill_value_to_html

        return quill_value_to_html(obj.body_en)


def _resolve_request_language(request) -> str:
    from jizz.update_i18n import resolve_request_language

    return resolve_request_language(request)


class UpdateListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)
    reactions = ReactionSerializer(many=True, read_only=True)
    thumbs_up_count = serializers.IntegerField(read_only=True)
    user_has_thumbs_up = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Update
        fields = (
            'id',
            'created',
            'title',
            'message',
            'excerpt',
            'user',
            'reactions',
            'thumbs_up_count',
            'user_has_thumbs_up',
        )

    def _language(self):
        return self.context.get('language') or _resolve_request_language(self.context.get('request'))

    def get_title(self, obj):
        return obj.title_for_language(self._language())

    def get_message(self, obj):
        from jizz.update_emails import plain_text_from_quill

        return plain_text_from_quill(obj.body_for_language(self._language()))

    def get_excerpt(self, obj):
        from jizz.update_emails import excerpt_from_html, quill_value_to_html

        html = quill_value_to_html(obj.body_for_language(self._language()))
        return excerpt_from_html(html)


class UpdateDetailSerializer(UpdateListSerializer):
    body = serializers.SerializerMethodField()
    body_en = serializers.SerializerMethodField()
    body_nl = serializers.SerializerMethodField()
    title_en = serializers.CharField(read_only=True)
    title_nl = serializers.CharField(read_only=True)

    class Meta(UpdateListSerializer.Meta):
        fields = UpdateListSerializer.Meta.fields + (
            'body',
            'body_en',
            'body_nl',
            'title_en',
            'title_nl',
        )

    def get_body(self, obj):
        from jizz.update_emails import quill_value_to_json_string

        return quill_value_to_json_string(obj.body_for_language(self._language()))

    def get_body_en(self, obj):
        from jizz.update_emails import quill_value_to_json_string

        return quill_value_to_json_string(obj.body_en)

    def get_body_nl(self, obj):
        from jizz.update_emails import quill_value_to_json_string

        return quill_value_to_json_string(obj.body_nl)


class PlayerSerializer(serializers.ModelSerializer):
    last_answer = AnswerSerializer(read_only=True)

    class Meta:
        model = Player
        fields = ('id', 'name', 'token', 'language', 'score', 'last_answer')

    def validate_name(self, value):
        from jizz.user_names import sanitize_player_name

        return sanitize_player_name(value.strip())


class MultiPlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ('id', 'name', 'language', 'score')


class PlayerScoreSerializer(serializers.ModelSerializer):
    last_answer = AnswerSerializer(read_only=True)
    name = serializers.CharField(source='player.name')
    language = serializers.CharField(source='player.language')
    media = serializers.CharField(source='game.media')
    level = serializers.CharField(source='game.level')
    length = serializers.CharField(source='game.length')
    country = CountrySerializer(source='game.country')
    created = serializers.DateTimeField(source='game.created')
    ranking = serializers.IntegerField(read_only=True)
    answers = AnswerSerializer(read_only=True, many=True)
    is_host = serializers.SerializerMethodField()

    def get_is_host(self, obj):
        """Check if this player is the host of the game"""
        return obj.game.host_id == obj.player_id

    def get_last_answer(self, obj):
        answer = obj.last_answer
        if answer is None:
            return None
        return AnswerSerializer(answer, context={'game': obj.game, **self.context}).data

    class Meta:
        model = PlayerScore
        fields = (
            'id', 'name', 'status', 'language', 'created',
            'score', 'last_answer', 'answers',
            'media', 'level', 'length',
            'country', 'ranking', 'is_host'
        )


class PlayerScoreListSerializer(serializers.ModelSerializer):
    """Minimal serializer for hiscores list: player name, country code, media, length, score (+ ranking, level for table)."""
    name = serializers.CharField(source='player.name', read_only=True)
    country = serializers.SerializerMethodField()
    media = serializers.CharField(source='game.media', read_only=True)
    level = serializers.CharField(source='game.level', read_only=True)
    length = serializers.IntegerField(source='game.length', read_only=True)
    rarity = serializers.CharField(source='game.rarity', read_only=True)
    ranking = serializers.IntegerField(source='score_rank', read_only=True)
    is_mine = serializers.SerializerMethodField()

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request is None:
            return False
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            return obj.player.user_id == user.id
        token = getattr(request, 'auth', None)
        if token:
            return str(obj.player.token) == str(token)
        return False

    def get_country(self, obj):
        if obj.game and obj.game.country_id:
            return {'code': obj.game.country.code, 'name': obj.game.country.name}
        return {'code': '', 'name': ''}

    class Meta:
        model = PlayerScore
        fields = ('id', 'name', 'country', 'media', 'level', 'length', 'rarity', 'score', 'ranking', 'is_mine')


class GameSerializer(serializers.ModelSerializer):
    country = serializers.CharField(write_only=True, required=False)
    country_data = CountrySerializer(source='country', read_only=True)
    host = MultiPlayerSerializer(read_only=True)
    current_highscore = PlayerScoreSerializer(read_only=True)
    scores = PlayerScoreSerializer(
        many=True, 
        read_only=True
    )

    def to_internal_value(self, data):
        if isinstance(data, dict) and 'rarity' not in data and 'include_rare' in data:
            data = data.copy()
            from jizz.models import Game
            data['rarity'] = (
                Game.RARIT_REGULAR if data.get('include_rare') else Game.RARIT_FAMILIAR
            )
        return super().to_internal_value(data)

    def create(self, validated_data):
        # Handle country field - convert code to Country object
        country_code = validated_data.pop('country', None)
        if country_code:
            validated_data['country'] = Country.objects.get(code=country_code)
        return super().create(validated_data)
    
    def to_representation(self, instance):
        # Use country_data for read operations
        representation = super().to_representation(instance)
        if 'country_data' in representation:
            representation['country'] = representation.pop('country_data')
        if instance.game_type in (
            Game.GAME_TYPE_PAIR_PRACTICE,
            Game.GAME_TYPE_SPECIES_PRACTICE,
        ):
            representation['current_highscore'] = None
        if instance.pair_species_low_id and instance.pair_species_high_id:
            from jizz.services.checklist import localized_species_names, normalize_species_language
            from jizz.services.species_cover import species_cover_url

            request = self.context.get('request')
            pair_ids = [instance.pair_species_low_id, instance.pair_species_high_id]
            species_by_id = Species.objects.in_bulk(pair_ids)
            lang = normalize_species_language(instance.language or 'en')
            display_names = localized_species_names(species_by_id, lang)
            low = species_by_id.get(instance.pair_species_low_id)
            high = species_by_id.get(instance.pair_species_high_id)
            representation['pair_species_low_name'] = display_names.get(
                instance.pair_species_low_id,
                low.name if low else '',
            )
            representation['pair_species_high_name'] = display_names.get(
                instance.pair_species_high_id,
                high.name if high else '',
            )
            representation['pair_species_low_code'] = (low.code or '') if low else ''
            representation['pair_species_high_code'] = (high.code or '') if high else ''
            representation['pair_species_low_illustration_url'] = (
                species_cover_url(low, request) if low else None
            )
            representation['pair_species_high_illustration_url'] = (
                species_cover_url(high, request) if high else None
            )
        if instance.focus_species_id:
            from jizz.services.checklist import localized_species_names, normalize_species_language
            from jizz.services.species_cover import species_cover_url

            request = self.context.get('request')
            focus = Species.objects.filter(pk=instance.focus_species_id).first()
            if focus:
                lang = normalize_species_language(instance.language or 'en')
                display_names = localized_species_names({focus.id: focus}, lang)
                representation['focus_species_name'] = display_names.get(focus.id, focus.name)
                representation['focus_species_code'] = focus.code or ''
                representation['focus_species_illustration_url'] = species_cover_url(
                    focus, request
                )
        return representation

    class Meta:
        model = Game
        fields = (
            'token', 'country', 'country_data', 'level', 'language',
            'created', 'multiplayer',
            'length', 'progress',
            'media', 'repeat',
            'host', 'ended',
            'current_highscore',
            'tax_order',
            'tax_family',
            'species_group',
            'season',
            'rarity',
            'include_escapes',
            'dificult_species',
            'game_type',
            'pair_species_low_id',
            'pair_species_high_id',
            'focus_species_id',
            'speed_seconds',
            'scores'
        )


class GameLanguageSerializer(serializers.ModelSerializer):
    """PATCH /api/games/<token>/ — bird-name language for an in-progress game."""

    class Meta:
        model = Game
        fields = ('language',)


class UserGameSerializer(serializers.ModelSerializer):
    """Serializer for games in user's games list, includes user's score and correct count"""
    country = CountrySerializer()
    user_score = serializers.SerializerMethodField()
    correct_count = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    
    def get_user_score(self, obj):
        """Get the user's total score for this game"""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return 0
        
        user_players = Player.objects.filter(user=request.user)
        player_score = PlayerScore.objects.filter(
            player__in=user_players,
            game=obj
        ).first()
        
        if player_score:
            return player_score.score
        return 0
    
    def get_correct_count(self, obj):
        """Get the number of correct answers for this user"""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return 0
        
        user_players = Player.objects.filter(user=request.user)
        user_player_scores = PlayerScore.objects.filter(player__in=user_players, game=obj)
        
        # Count correct answers for this user's player scores in this game
        correct_count = Answer.objects.filter(
            player_score__in=user_player_scores,
            correct=True
        ).count()
        
        return correct_count
    
    def get_total_questions(self, obj):
        """Get the total number of questions in this game"""
        return obj.questions.count()
    
    class Meta:
        model = Game
        fields = (
            'token', 'country', 'level', 'language',
            'created', 'multiplayer',
            'length', 'progress',
            'media', 'repeat',
            'host', 'ended',
            'tax_order',
            'tax_family',
            'species_group',
            'season',
            'rarity',
            'include_escapes',
            'dificult_species',
            'user_score',
            'correct_count',
            'total_questions'
        )


class QuestionWithAnswerSerializer(serializers.ModelSerializer):
    """Serializer for question with user's answer, timing, and score"""
    species = serializers.SerializerMethodField()
    user_answer = serializers.SerializerMethodField()
    time_taken_seconds = serializers.SerializerMethodField()
    points = serializers.SerializerMethodField()
    correct = serializers.SerializerMethodField()
    media_item = serializers.SerializerMethodField()
    
    def get_species(self, obj):
        """Get species with game language context"""
        serializer = SpeciesDetailSerializer(
            obj.species,
            context={'game': obj.game, **self.context}
        )
        return serializer.data
    
    def _get_user_answer_obj(self, obj):
        """Helper method to get the user's answer object (uses prefetched data)"""
        detail_player = self.context.get('detail_player')
        if detail_player is not None:
            if hasattr(obj, 'answers'):
                for answer in obj.answers.all():
                    if (
                        answer.player_score
                        and answer.player_score.player_id == detail_player.id
                    ):
                        return answer
            return (
                Answer.objects.filter(
                    player_score__player=detail_player,
                    player_score__game=obj.game,
                    question=obj,
                )
                .select_related('answer')
                .first()
            )

        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return None

        # Try to use prefetched answers first
        if hasattr(obj, 'answers'):
            # Answers are prefetched, find the one for this user
            for answer in obj.answers.all():
                if answer.player_score and answer.player_score.player.user == request.user:
                    return answer

        # Fallback: query if not prefetched
        game = obj.game
        user_players = Player.objects.filter(user=request.user)
        player_score = PlayerScore.objects.filter(
            player__in=user_players,
            game=game
        ).first()

        if not player_score:
            return None

        # Get the answer for this question
        answer = Answer.objects.filter(
            player_score=player_score,
            question=obj
        ).select_related('answer').first()

        return answer
    
    def get_user_answer(self, obj):
        """Get the user's answer for this question"""
        answer = self._get_user_answer_obj(obj)
        
        if answer:
            # Return full species data including images, videos, sounds, and code
            species = answer.answer
            return {
                'id': species.id,
                'name': species.name,
                'name_latin': species.name_latin,
                'name_nl': species.name_nl if hasattr(species, 'name_nl') else '',
                'code': species.code,
                'images': QuestionMediaSerializer(species.images.all(), many=True).data,
                'videos': QuestionMediaSerializer(species.videos.all(), many=True).data,
                'sounds': QuestionMediaSerializer(species.sounds.all(), many=True).data,
            }
        return None
    
    def get_time_taken_seconds(self, obj):
        """Seconds from question (or media-ready) to submit — same basis as score calculation."""
        answer = self._get_user_answer_obj(obj)

        if answer:
            start = obj.created
            player_id = answer.player_score.player_id
            ready = None
            for mr in obj.media_ready.all():
                if mr.player_id == player_id:
                    ready = mr
                    break
            if ready is None:
                ready = QuestionMediaReady.objects.filter(
                    question=obj,
                    player_id=player_id,
                ).first()
            if ready and ready.ready_at:
                start = max(start, ready.ready_at)
            time_taken = (answer.created - start).total_seconds()
            return round(max(0.0, time_taken), 2)
        return None
    
    def get_points(self, obj):
        """Get points earned for this question"""
        answer = self._get_user_answer_obj(obj)
        
        if answer:
            return answer.score
        return None
    
    def get_correct(self, obj):
        """Check if the answer was correct"""
        answer = self._get_user_answer_obj(obj)
        
        if answer:
            return answer.correct
        return None
    
    def get_media_item(self, obj):
        """Get the specific media item (image, video, or sound) that was used for this question"""
        game = obj.game
        media_type = game.media
        media_index = obj.number
        
        if media_type == 'images':
            images = obj.species.images.all()
            if media_index < images.count():
                image = images[media_index]
                return {
                    'type': 'image',
                    'url': media_display_url(image.url),
                    'link': image.link,
                    'contributor': image.contributor,
                }
        elif media_type == 'video':
            videos = obj.species.videos.all()
            if media_index < videos.count():
                video = videos[media_index]
                return {
                    'type': 'video',
                    'url': media_display_url(video.url),
                    'link': video.link,
                    'contributor': video.contributor,
                }
        elif media_type == 'audio':
            sounds = obj.species.sounds.all()
            if media_index < sounds.count():
                sound = sounds[media_index]
                return {
                    'type': 'audio',
                    'url': sound.url,
                    'link': sound.link,
                    'contributor': sound.contributor,
                }
        
        return None
    
    class Meta:
        model = Question
        fields = (
            'id', 'sequence', 'number', 'species',
            'user_answer', 'time_taken_seconds', 'points', 'correct',
            'created', 'media_item'
        )


class GameDetailWithAnswersSerializer(serializers.ModelSerializer):
    """Serializer for game with all questions and user's answers"""
    country = CountrySerializer()
    questions = serializers.SerializerMethodField()
    total_score = serializers.SerializerMethodField()
    
    def get_questions(self, obj):
        """Get questions ordered by sequence"""
        questions = obj.questions.all().order_by('sequence')
        # Pass game context to serializer for language-based translations
        context = {**self.context, 'game': obj}
        return QuestionWithAnswerSerializer(questions, many=True, context=context).data
    
    def get_total_score(self, obj):
        """Get total score for the user"""
        detail_player = self.context.get('detail_player')
        if detail_player is not None:
            ps = PlayerScore.objects.filter(player=detail_player, game=obj).first()
            return ps.score if ps else 0

        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return 0

        user_players = Player.objects.filter(user=request.user)
        player_score = PlayerScore.objects.filter(
            player__in=user_players,
            game=obj
        ).first()

        if player_score:
            return player_score.score
        return 0
    
    class Meta:
        model = Game
        fields = (
            'token', 'country', 'level', 'language',
            'created', 'multiplayer',
            'length', 'progress',
            'media', 'repeat',
            'ended',
            'tax_order',
            'tax_family',
            'species_group',
            'season',
            'rarity',
            'include_escapes',
            'dificult_species',
            'questions',
            'total_score'
        )


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ('code', 'name')


_LEGACY_GITHUB_REPOS = (
    'https://github.com/gannetson/birdr',
    'http://github.com/gannetson/birdr',
)
_CURRENT_GITHUB_REPO = 'https://github.com/birdr-app/birdr'


def _rewrite_legacy_github_repo(value):
    """Point About/help CMS content at the public Birdr repo."""
    if not isinstance(value, str) or not value:
        return value
    updated = value
    for old in _LEGACY_GITHUB_REPOS:
        updated = updated.replace(old, _CURRENT_GITHUB_REPO)
    return updated


class PageSerializer(serializers.ModelSerializer):
    content = serializers.SerializerMethodField()

    def get_content(self, obj):
        """Return Quill content as JSON string (delta + html) for frontend."""
        val = obj.content
        if hasattr(val, 'json_string'):
            raw = val.json_string
        elif isinstance(val, str):
            raw = val
        else:
            raw = val if val is not None else '{"delta":"","html":""}'
        return _rewrite_legacy_github_repo(raw)

    class Meta:
        model = Page
        fields = ('id', 'title', 'slug', 'content', 'show')


class PageListSerializer(serializers.ModelSerializer):
    """Minimal serializer for help overview (no content)."""
    class Meta:
        model = Page
        fields = ('id', 'title', 'slug')


class FeedbackSerializer(serializers.ModelSerializer):
    comment = serializers.CharField(trim_whitespace=True)
    player_token = serializers.CharField(required=False, write_only=True, allow_blank=True)
    rating = serializers.IntegerField(required=False, default=0)

    def validate_comment(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError('This field is required.')
        return str(value).strip()

    def create(self, validated_data):
        player_token = (validated_data.pop('player_token', None) or '').strip()
        request = self.context.get('request')

        player = Player.objects.filter(token=player_token).first() if player_token else None
        user = None
        if request and request.user and request.user.is_authenticated:
            user = request.user
            if not player:
                player = Player.objects.filter(user=user).first()

        feedback = Feedback.objects.create(
            player=player,
            user=user,
            **validated_data,
        )
        from jizz.feedback_email import send_feedback_notification

        send_feedback_notification(feedback)
        return feedback

    class Meta:
        model = Feedback
        fields = ('comment', 'player_token', 'rating', 'created')


# --- Birdr Journey ---


class JourneyStepSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    resolved_family_name_latin = serializers.SerializerMethodField()
    resolved_family_name = serializers.SerializerMethodField()
    resolved_family_description = serializers.SerializerMethodField()

    class Meta:
        model = JourneyStep
        fields = [
            'id',
            'sequence',
            'step_type',
            'level',
            'length',
            'jokers',
            'rarity',
            'media',
            'include_escapes',
            'speed_seconds',
            'status',
            'resolved_family_name_latin',
            'resolved_family_name',
            'resolved_family_description',
        ]

    def get_status(self, obj):
        step_statuses = self.context.get('step_statuses') or {}
        return step_statuses.get(obj.id, 'locked')

    def _resolved_family(self, obj):
        from jizz.services.journey_family import (
            family_by_latin,
            family_display_fields,
            is_family_step,
            resolve_family_for_step,
        )

        if not is_family_step(obj):
            return None

        journey = self.context.get('journey')
        if not journey:
            return None

        step_tax_families = self.context.get('step_tax_families') or {}
        tax_family = step_tax_families.get(obj.id)
        family = family_by_latin(tax_family) if tax_family else None
        if not family:
            family = resolve_family_for_step(
                obj,
                journey.country,
                level_steps=self.context.get('level_steps'),
            )
        if not family:
            return None

        language = self.context.get('language', 'en')
        return family_display_fields(family, language)

    def get_resolved_family_name_latin(self, obj):
        resolved = self._resolved_family(obj)
        return resolved['name_latin'] if resolved else None

    def get_resolved_family_name(self, obj):
        resolved = self._resolved_family(obj)
        return resolved['name'] if resolved else None

    def get_resolved_family_description(self, obj):
        resolved = self._resolved_family(obj)
        return resolved['description'] if resolved else None


class JourneyLevelSerializer(serializers.ModelSerializer):
    icon_url = serializers.SerializerMethodField()
    is_champion = serializers.SerializerMethodField()
    steps = serializers.SerializerMethodField()

    class Meta:
        model = JourneyLevel
        fields = [
            'sequence',
            'title',
            'description',
            'title_nl',
            'description_nl',
            'icon_url',
            'is_champion',
            'steps',
        ]

    def get_icon_url(self, obj):
        if not obj.icon:
            return None
        from jizz.services.species_cover import absolute_media_url

        request = self.context.get('request')
        return absolute_media_url(obj.icon.url, request)

    def get_is_champion(self, obj):
        return obj.is_champion

    def get_steps(self, obj):
        if not self.context.get('include_steps', True):
            return []
        steps = list(obj.steps.order_by('sequence'))
        ctx = dict(self.context)
        ctx['level_steps'] = steps
        return JourneyStepSerializer(steps, many=True, context=ctx).data


class BirdrJourneyGameSerializer(serializers.ModelSerializer):
    journey_step = JourneyStepSerializer(read_only=True)
    remaining_jokers = serializers.IntegerField(read_only=True)
    game = GameSerializer(read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = BirdrJourneyGame
        fields = ['id', 'journey_step', 'game', 'created', 'status', 'remaining_jokers']


class BirdrJourneyListSerializer(serializers.ModelSerializer):
    """Lightweight payload for the country-challenge overview list."""

    country = CountrySerializer(read_only=True)
    player_token = serializers.SerializerMethodField()
    is_champion = serializers.SerializerMethodField()
    current_level = serializers.SerializerMethodField()

    class Meta:
        model = BirdrJourney
        fields = [
            'id',
            'country',
            'player_token',
            'current_sequence',
            'is_champion',
            'current_level',
            'updated',
        ]

    def _levels(self):
        levels = self.context.get('journey_levels')
        if levels is None:
            from jizz.birdr_journey_views import get_journey_levels_ordered

            levels = get_journey_levels_ordered()
            self.context['journey_levels'] = levels
        return levels

    def _level_at(self, sequence):
        levels = self._levels()
        if sequence < 0 or sequence >= len(levels):
            return None
        return levels[sequence]

    def get_player_token(self, obj):
        token = self.context.get('player_token')
        if token is not None:
            return token
        from jizz.birdr_journey_views import get_journey_host

        host = get_journey_host(obj)
        return str(host.token) if host else None

    def get_is_champion(self, obj):
        level = self._level_at(obj.current_sequence)
        return bool(level and len(level.steps.all()) == 0)

    def get_current_level(self, obj):
        level = self._level_at(obj.current_sequence)
        if not level:
            return None
        from jizz.services.species_cover import absolute_media_url

        request = self.context.get('request')
        icon_url = absolute_media_url(level.icon.url, request) if level.icon else None
        return {
            'sequence': level.sequence,
            'title': level.title,
            'title_nl': level.title_nl or '',
            'icon_url': icon_url,
            'is_champion': len(level.steps.all()) == 0,
            'steps': [],
        }


class BirdrJourneySerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    player_token = serializers.SerializerMethodField()
    current_level = serializers.SerializerMethodField()
    next_level = serializers.SerializerMethodField()
    active_step = serializers.SerializerMethodField()
    is_champion = serializers.SerializerMethodField()
    pending_level_celebration = serializers.SerializerMethodField()
    can_play_today = serializers.SerializerMethodField()
    current_game = serializers.SerializerMethodField()

    class Meta:
        model = BirdrJourney
        fields = [
            'id',
            'country',
            'player_token',
            'current_sequence',
            'current_step_sequence',
            'streak_days',
            'last_played_date',
            'can_play_today',
            'is_champion',
            'pending_level_celebration',
            'current_level',
            'next_level',
            'active_step',
            'current_game',
            'created',
            'updated',
        ]

    def get_player_token(self, obj):
        from jizz.birdr_journey_views import get_journey_host

        host = get_journey_host(obj)
        return str(host.token) if host else None

    def _serializer_context(self):
        journey = self.instance
        from jizz.birdr_journey_views import compute_step_statuses, get_journey_host, get_journey_level

        ctx = dict(self.context)
        ctx['step_statuses'] = compute_step_statuses(journey)
        ctx['include_steps'] = True
        ctx['journey'] = journey

        request = self.context.get('request')
        language = request.query_params.get('language') if request else None
        if not language:
            host = get_journey_host(journey)
            language = getattr(host, 'language', 'en') or 'en'
        if journey.user_id:
            try:
                language = journey.user.profile.language or language
            except Exception:
                pass
        ctx['language'] = language or 'en'

        level = get_journey_level(journey.current_sequence)
        if level:
            ctx['level_steps'] = list(level.steps.order_by('sequence'))

        step_tax_families = {}
        for journey_game in journey.games.select_related('game', 'journey_step').all():
            if journey_game.game.tax_family:
                step_tax_families[journey_game.journey_step_id] = journey_game.game.tax_family
        ctx['step_tax_families'] = step_tax_families

        return ctx

    def _level_for_sequence(self, sequence):
        from jizz.birdr_journey_views import get_journey_level

        return get_journey_level(sequence)

    def get_current_level(self, obj):
        level = self._level_for_sequence(obj.current_sequence)
        if not level:
            return None
        return JourneyLevelSerializer(level, context=self._serializer_context()).data

    def get_next_level(self, obj):
        level = self._level_for_sequence(obj.current_sequence + 1)
        if not level:
            return None
        ctx = dict(self._serializer_context())
        ctx['include_steps'] = False
        return JourneyLevelSerializer(level, context=ctx).data

    def get_active_step(self, obj):
        from jizz.birdr_journey_views import get_active_journey_step, get_journey_level

        step = get_active_journey_step(obj)
        if not step:
            return None
        ctx = self._serializer_context()
        level = get_journey_level(obj.current_sequence)
        if level:
            ctx['level_steps'] = list(level.steps.order_by('sequence'))
        return JourneyStepSerializer(step, context=ctx).data

    def get_is_champion(self, obj):
        level = self._level_for_sequence(obj.current_sequence)
        return bool(level and level.is_champion)

    def get_pending_level_celebration(self, obj):
        from jizz.birdr_journey_views import is_pending_level_celebration

        return is_pending_level_celebration(obj)

    def get_can_play_today(self, obj):
        from jizz.birdr_journey_views import get_active_journey_step, is_pending_level_celebration

        if is_pending_level_celebration(obj):
            return False
        level = self._level_for_sequence(obj.current_sequence)
        if not level or level.is_champion:
            return False
        return get_active_journey_step(obj) is not None

    def get_current_game(self, obj):
        from jizz.birdr_journey_views import get_current_journey_game, get_journey_game_by_token

        ctx = self._serializer_context()
        request = self.context.get('request')
        game_token = (request.query_params.get('game_token') or '').strip() if request else ''
        if game_token:
            journey_game = get_journey_game_by_token(obj, game_token)
            if journey_game:
                return BirdrJourneyGameSerializer(journey_game, context=ctx).data

        journey_game = get_current_journey_game(obj)
        if not journey_game:
            return None
        return BirdrJourneyGameSerializer(journey_game, context=ctx).data


# --- Friends & Daily Challenge ---


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user for friend lists and challenge participants."""
    username = serializers.CharField(read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'profile')

    def get_profile(self, obj):
        try:
            p = obj.profile
            return {
                'username': obj.username,
                'language': getattr(p, 'language', None),
                'country_code': p.country_id if p and p.country_id else None,
            }
        except UserProfile.DoesNotExist:
            return {'username': obj.username}


class FriendshipSerializer(serializers.ModelSerializer):
    from_user = UserMinimalSerializer(read_only=True)
    to_user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Friendship
        fields = ('id', 'from_user', 'to_user', 'status', 'created')
        read_only_fields = ('id', 'created')


class FriendshipRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    username = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs.get('user_id') and not attrs.get('username'):
            raise serializers.ValidationError('Provide user_id or username')
        return attrs


class DailyChallengeParticipantSerializer(serializers.ModelSerializer):
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = DailyChallengeParticipant
        fields = ('id', 'user', 'invited_by', 'status', 'accepted_at', 'created')


class DailyChallengeRoundSerializer(serializers.ModelSerializer):
    game_token = serializers.SerializerMethodField()
    my_player_token = serializers.SerializerMethodField()
    game_ended = serializers.SerializerMethodField()
    user_score = serializers.SerializerMethodField()
    points_multiplier = serializers.SerializerMethodField()
    display_score = serializers.SerializerMethodField()
    opens_at_local = serializers.SerializerMethodField()
    closes_at_local = serializers.SerializerMethodField()

    class Meta:
        model = DailyChallengeRound
        fields = (
            'id', 'day_number', 'game', 'game_token', 'my_player_token',
            'game_ended', 'user_score', 'points_multiplier', 'display_score',
            'opens_at', 'closes_at', 'opens_at_local', 'closes_at_local',
            'status', 'created'
        )

    @staticmethod
    def _points_multiplier_for_day(day_number):
        if day_number == 3:
            return 2
        if day_number == 7:
            return 3
        return 1

    def get_points_multiplier(self, obj):
        return self._points_multiplier_for_day(obj.day_number)

    def get_display_score(self, obj):
        raw = self.get_user_score(obj)
        if raw is None:
            return None
        return raw * self._points_multiplier_for_day(obj.day_number)

    def get_game_token(self, obj):
        return obj.game.token if obj.game_id else None

    def get_my_player_token(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not obj.game_id:
            return None
        from jizz.models import Player
        player = Player.objects.filter(user=request.user).filter(scores__game=obj.game).first()
        return player.token if player else None

    def get_game_ended(self, obj):
        if not obj.game_id or not obj.game:
            return False
        if obj.status == 'completed':
            return True
        return getattr(obj.game, 'ended', False) if hasattr(obj.game, 'ended') else False

    def get_user_score(self, obj):
        if not obj.game_id:
            return None
        request = self.context.get('request')
        if not request or not request.user:
            return None
        from jizz.models import Player
        player = Player.objects.filter(user=request.user).filter(scores__game=obj.game).first()
        if not player:
            return None
        ps = PlayerScore.objects.filter(player=player, game=obj.game).first()
        return ps.score if ps is not None else None

    def get_opens_at_local(self, obj):
        if not obj.opens_at:
            return None
        request = self.context.get('request')
        if not request or not request.user:
            return None
        try:
            profile = UserProfile.objects.filter(user=request.user).first()
            tz_name = (profile.timezone if profile else 'Europe/Amsterdam') or 'Europe/Amsterdam'
            tz_name = (tz_name or '').strip() or 'Europe/Amsterdam'
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(tz_name)
            return obj.opens_at.astimezone(tz).isoformat()
        except Exception:
            return None

    def get_closes_at_local(self, obj):
        if not obj.closes_at:
            return None
        request = self.context.get('request')
        if not request or not request.user:
            return None
        try:
            profile = UserProfile.objects.filter(user=request.user).first()
            tz_name = (profile.timezone if profile else 'Europe/Amsterdam') or 'Europe/Amsterdam'
            tz_name = (tz_name or '').strip() or 'Europe/Amsterdam'
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(tz_name)
            return obj.closes_at.astimezone(tz).isoformat()
        except Exception:
            return None


class DailyChallengeSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    country_code = serializers.SlugRelatedField(
        slug_field='code',
        queryset=Country.objects.all(),
        write_only=True,
        required=False
    )
    participants = DailyChallengeParticipantSerializer(many=True, read_only=True)
    rounds = DailyChallengeRoundSerializer(many=True, read_only=True)
    creator_username = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = DailyChallenge
        fields = (
            'id', 'token', 'creator', 'creator_username', 'country', 'country_code',
            'media', 'length', 'duration_days', 'level', 'started_at', 'status',
            'participants', 'rounds', 'created'
        )
        read_only_fields = ('token', 'creator', 'started_at', 'participants', 'rounds')


class DailyChallengeCreateSerializer(serializers.Serializer):
    country = serializers.CharField()
    media = serializers.ChoiceField(choices=Game.MEDIA_CHOICES, default='images')
    length = serializers.IntegerField(default=10)
    duration_days = serializers.IntegerField(default=7, required=False)
    level = serializers.CharField(default='advanced', required=False)


class DailyChallengeInviteSerializer(serializers.Serializer):
    friend_user_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    emails = serializers.ListField(child=serializers.EmailField(), required=False, default=list)


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ('id', 'token', 'platform', 'created', 'last_used')
        read_only_fields = ('id', 'created', 'last_used')
