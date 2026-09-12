"""Serializers for personal practice stats and drill game endpoints."""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from jizz.game_question_selection import (
    candidate_species_ids,
    count_eligible_media,
    media_type_for_game,
    species_practice_target_pool_ids,
)
from jizz.models import Country, Game, Player, PlayerScore, Species
from jizz.quiz_mistake_stats import (
    get_user_fixed_confusion_pair_keys,
    get_user_fixed_species_ids,
    get_user_trouble_spot_rows,
    normalize_country_filter,
)
from jizz.serializers import GameSerializer
from jizz.services.checklist import localized_species_names, normalize_species_language
from jizz.services.species_cover import species_cover_urls_bulk
from jizz.user_names import player_name_for_user


def user_preferred_language(user, request) -> str:
    language = (request.query_params.get('language') or '').strip()
    if not language:
        try:
            language = (user.profile.language or '').strip()
        except Exception:
            language = ''
    if not language:
        player = Player.objects.filter(user=user).order_by('id').first()
        if player and player.language:
            language = player.language
    if not language:
        language = 'en'
    return normalize_species_language(language)


def get_or_create_player_for_user(user) -> Player:
    player = Player.objects.filter(user=user).first()
    if player:
        return player
    return Player.objects.create(
        user=user,
        name=player_name_for_user(user),
        language=getattr(getattr(user, 'profile', None), 'language', None) or 'en',
    )


def resolve_practice_country(user, country_code: str | None) -> Country:
    code = normalize_country_filter(country_code)
    if not code:
        try:
            profile_country = user.profile.country_id
        except Exception:
            profile_country = None
        code = normalize_country_filter(profile_country)
    if not code:
        raise ValidationError(
            {'country_code': 'Country is required (set profile country or pass country_code).'}
        )
    return Country.objects.get(pk=code)


def canonical_pair_ids(low_id: int, high_id: int) -> tuple[int, int]:
    if low_id == high_id:
        raise ValidationError({'error': 'Pair species must be different.'})
    return (low_id, high_id) if low_id < high_id else (high_id, low_id)


def validate_pair_for_country(country: Country, low_id: int, high_id: int) -> None:
    from jizz.quiz_mistake_stats import _allowed_species_ids_for_country

    allowed = _allowed_species_ids_for_country(country.code)
    if low_id not in allowed or high_id not in allowed:
        raise ValidationError({'error': 'Both species must be on your country checklist.'})

    media_type = media_type_for_game(Game(country=country, media='images'))
    for sid in (low_id, high_id):
        if count_eligible_media(sid, media_type) <= 0:
            raise ValidationError({'error': 'Both species need eligible images for this country.'})


def validate_species_for_country(country: Country, species_id: int) -> None:
    from jizz.quiz_mistake_stats import _allowed_species_ids_for_country

    allowed = _allowed_species_ids_for_country(country.code)
    if species_id not in allowed:
        raise ValidationError({'error': 'Species must be on your country checklist.'})

    media_type = media_type_for_game(Game(country=country, media='images'))
    if count_eligible_media(species_id, media_type) <= 0:
        raise ValidationError({'error': 'Species needs eligible images for this country.'})


def _profile_language(user) -> str:
    try:
        return user.profile.language or 'en'
    except Exception:
        return 'en'


class TroubleSpotSpeciesSerializer(serializers.Serializer):
    species_id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    name_translated = serializers.SerializerMethodField()
    name_latin = serializers.SerializerMethodField()
    name_nl = serializers.SerializerMethodField()
    times_shown = serializers.IntegerField()
    correctly_answered = serializers.IntegerField()
    wrongly_answered = serializers.IntegerField()
    correct_rate = serializers.FloatField(allow_null=True)
    error_rate = serializers.FloatField(allow_null=True)
    illustration_url = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()
    fixed = serializers.SerializerMethodField()

    def _species(self, row: dict) -> Species | None:
        return (self.context.get('species_by_id') or {}).get(row['species_id'])

    def _display_name(self, row: dict) -> str:
        display_names = self.context.get('display_names') or {}
        return display_names.get(row['species_id'], row.get('name', ''))

    def get_name(self, row: dict) -> str:
        return self._display_name(row)

    def get_name_translated(self, row: dict) -> str:
        return self._display_name(row)

    def get_name_latin(self, row: dict) -> str:
        species = self._species(row)
        if species:
            return species.name_latin
        return row.get('name_latin', '')

    def get_name_nl(self, row: dict) -> str:
        species = self._species(row)
        return (species.name_nl or '') if species else ''

    def get_illustration_url(self, row: dict) -> str | None:
        urls = self.context.get('illustration_urls') or {}
        return urls.get(row['species_id'])

    def get_code(self, row: dict) -> str:
        species = self._species(row)
        return (species.code or '') if species else ''

    def get_fixed(self, row: dict) -> bool:
        fixed_species = self.context.get('fixed_species') or set()
        return row['species_id'] in fixed_species


class TroubleSpotPairSerializer(serializers.Serializer):
    low_id = serializers.IntegerField()
    high_id = serializers.IntegerField()
    total_wrong = serializers.IntegerField()
    when_low_was_target = serializers.IntegerField()
    when_high_was_target = serializers.IntegerField()
    low_name = serializers.SerializerMethodField()
    high_name = serializers.SerializerMethodField()
    low_name_translated = serializers.SerializerMethodField()
    high_name_translated = serializers.SerializerMethodField()
    low_name_latin = serializers.SerializerMethodField()
    high_name_latin = serializers.SerializerMethodField()
    low_name_nl = serializers.SerializerMethodField()
    high_name_nl = serializers.SerializerMethodField()
    low_code = serializers.SerializerMethodField()
    high_code = serializers.SerializerMethodField()
    low_illustration_url = serializers.SerializerMethodField()
    high_illustration_url = serializers.SerializerMethodField()
    fixed = serializers.SerializerMethodField()

    def _display_name(self, species_id: int, fallback: str) -> str:
        display_names = self.context.get('display_names') or {}
        return display_names.get(species_id, fallback)

    def _species(self, species_id: int) -> Species | None:
        return (self.context.get('species_by_id') or {}).get(species_id)

    def get_low_name(self, row: dict) -> str:
        return self._display_name(row['low_id'], row.get('low_name', ''))

    def get_high_name(self, row: dict) -> str:
        return self._display_name(row['high_id'], row.get('high_name', ''))

    def get_low_name_translated(self, row: dict) -> str:
        return self.get_low_name(row)

    def get_high_name_translated(self, row: dict) -> str:
        return self.get_high_name(row)

    def get_low_name_latin(self, row: dict) -> str:
        species = self._species(row['low_id'])
        return species.name_latin if species else row.get('low_name_latin', '')

    def get_high_name_latin(self, row: dict) -> str:
        species = self._species(row['high_id'])
        return species.name_latin if species else row.get('high_name_latin', '')

    def get_low_name_nl(self, row: dict) -> str:
        species = self._species(row['low_id'])
        return (species.name_nl or '') if species else ''

    def get_high_name_nl(self, row: dict) -> str:
        species = self._species(row['high_id'])
        return (species.name_nl or '') if species else ''

    def get_low_code(self, row: dict) -> str:
        species = self._species(row['low_id'])
        return (species.code or '') if species else ''

    def get_high_code(self, row: dict) -> str:
        species = self._species(row['high_id'])
        return (species.code or '') if species else ''

    def get_low_illustration_url(self, row: dict) -> str | None:
        urls = self.context.get('illustration_urls') or {}
        return urls.get(row['low_id'])

    def get_high_illustration_url(self, row: dict) -> str | None:
        urls = self.context.get('illustration_urls') or {}
        return urls.get(row['high_id'])

    def get_fixed(self, row: dict) -> bool:
        fixed_pairs = self.context.get('fixed_pairs') or set()
        return (row['low_id'], row['high_id']) in fixed_pairs


class TroubleSpotsResponseSerializer(serializers.Serializer):
    country_code = serializers.CharField(allow_null=True)
    species = TroubleSpotSpeciesSerializer(many=True)
    pairs = TroubleSpotPairSerializer(many=True)

    @classmethod
    def for_user(cls, user, request):
        country_code = request.query_params.get('country_code') or request.query_params.get('country')
        cc = normalize_country_filter(country_code)
        if not cc:
            try:
                cc = normalize_country_filter(user.profile.country_id)
            except Exception:
                cc = None

        species_rows, pair_rows = get_user_trouble_spot_rows(user.id, cc)

        language = user_preferred_language(user, request)
        species_ids = [row['species_id'] for row in species_rows]
        pair_ids = {i for row in pair_rows for i in (row['low_id'], row['high_id'])}
        all_species_ids = list(set(species_ids) | pair_ids)
        species_by_id = Species.objects.in_bulk(all_species_ids)
        display_names = localized_species_names(species_by_id, language)
        illustration_urls = species_cover_urls_bulk(all_species_ids, request)
        fixed_pairs = get_user_fixed_confusion_pair_keys(user.id)
        fixed_species = get_user_fixed_species_ids(user.id)

        context = {
            'request': request,
            'species_by_id': species_by_id,
            'display_names': display_names,
            'illustration_urls': illustration_urls,
            'fixed_pairs': fixed_pairs,
            'fixed_species': fixed_species,
        }
        return cls(
            {
                'country_code': cc,
                'species': species_rows,
                'pairs': pair_rows,
            },
            context=context,
        )


class StartPracticeResponseSerializer(serializers.Serializer):
    game = GameSerializer()
    player_token = serializers.CharField()


class StartSpeciesPracticeSerializer(serializers.Serializer):
    species_id = serializers.IntegerField()
    country_code = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        user = self.context['request'].user
        species_id = attrs['species_id']

        if not Species.objects.filter(pk=species_id).exists():
            raise ValidationError({'error': 'Invalid species id.'})

        country = resolve_practice_country(user, attrs.get('country_code'))
        validate_species_for_country(country, species_id)

        probe = Game(
            country=country,
            level='advanced',
            media='images',
            rarity=Game.RARIT_EXCEPTIONAL,
            include_escapes=False,
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=species_id,
        )
        candidates = candidate_species_ids(probe)
        if species_id not in candidates:
            raise ValidationError(
                {'error': 'Species needs eligible images on your checklist for practice.'}
            )
        if len(candidates) < 2:
            raise ValidationError(
                {'error': 'Not enough species on your checklist to start practice.'}
            )
        if not species_practice_target_pool_ids(probe):
            raise ValidationError(
                {'error': 'Could not build a practice set for this species.'}
            )

        attrs['country'] = country
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        host = get_or_create_player_for_user(user)
        country = validated_data['country']
        species_id = validated_data['species_id']

        game = Game.objects.create(
            country=country,
            level='advanced',
            length=20,
            media='images',
            rarity=Game.RARIT_EXCEPTIONAL,
            include_escapes=False,
            multiplayer=False,
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=species_id,
            host=host,
            language=_profile_language(user),
        )
        PlayerScore.objects.get_or_create(player=host, game=game, defaults={'score': 0})
        request = self.context.get('request')
        if request is not None:
            from jizz.client_info import record_player_score_client_from_request

            record_player_score_client_from_request(host, game, request)
        game.add_question()
        return {'game': game, 'player': host}


class StartConfusionPairPracticeSerializer(serializers.Serializer):
    low_id = serializers.IntegerField()
    high_id = serializers.IntegerField()
    country_code = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        user = self.context['request'].user
        try:
            low_id = int(attrs['low_id'])
            high_id = int(attrs['high_id'])
        except (TypeError, ValueError) as exc:
            raise ValidationError({'error': 'low_id and high_id must be integers.'}) from exc

        low_id, high_id = canonical_pair_ids(low_id, high_id)
        if Species.objects.filter(id__in=[low_id, high_id]).count() != 2:
            raise ValidationError({'error': 'Invalid species ids.'})

        country = resolve_practice_country(user, attrs.get('country_code'))
        validate_pair_for_country(country, low_id, high_id)

        attrs['low_id'] = low_id
        attrs['high_id'] = high_id
        attrs['country'] = country
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        host = get_or_create_player_for_user(user)
        country = validated_data['country']

        game = Game.objects.create(
            country=country,
            level='beginner',
            length=20,
            media='images',
            rarity=Game.RARIT_REGULAR,
            include_escapes=False,
            multiplayer=False,
            game_type=Game.GAME_TYPE_PAIR_PRACTICE,
            pair_species_low_id=validated_data['low_id'],
            pair_species_high_id=validated_data['high_id'],
            host=host,
            language=_profile_language(user),
        )
        PlayerScore.objects.get_or_create(player=host, game=game, defaults={'score': 0})
        request = self.context.get('request')
        if request is not None:
            from jizz.client_info import record_player_score_client_from_request

            record_player_score_client_from_request(host, game, request)
        game.add_question()
        return {'game': game, 'player': host}
