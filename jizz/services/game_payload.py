"""Preload everything ``GameSerializer`` reads for a finished or running game.

A serialized game embeds its scores and the country high score, each with every
answer, and each answer with two species (media, translated name) and a frequency.
Without preloading that is several queries per answer. ``prepare_game_payload``
loads it in a fixed number of queries; the serialized output is unchanged.
"""

from __future__ import annotations

from django.db.models import Prefetch, prefetch_related_objects

from jizz.services.species_prime import prime_species


def _answers_prefetch():
    from jizz.models import Answer

    return Prefetch(
        'answers',
        queryset=Answer.objects.select_related(
            'question__species', 'question__game__country', 'answer',
        ),
    )


def _score_queryset():
    from jizz.models import PlayerScore

    return PlayerScore.objects.select_related('player', 'game__country', 'game__host').prefetch_related(
        _answers_prefetch()
    )


def _prime_frequencies(answers) -> None:
    """Store frequencies in the request memo, keyed by game country and species."""
    from jizz.models import CountrySpecies
    from jizz.request_memo import memo
    from jizz.species_frequency import country_codes_for_game

    store = memo()
    if store is None:
        return
    by_country = store.setdefault('species_frequency', {})
    species_by_country: dict[str, set[int]] = {}
    game_by_country = {}
    for answer in answers:
        game = answer.question.game
        if game.country_id:
            species_by_country.setdefault(game.country_id, set()).add(answer.question.species_id)
            game_by_country.setdefault(game.country_id, game)
    for country_id, species_ids in species_by_country.items():
        codes = country_codes_for_game(game_by_country[country_id])
        rows = CountrySpecies.objects.filter(
            country_id__in=codes, species_id__in=species_ids,
        ).values_list('country_id', 'species_id', 'frequency')
        found = {(country, species): freq for country, species, freq in rows}
        known = by_country.setdefault(country_id, {})
        for species_id in species_ids:
            known[species_id] = next((found[(c, species_id)] for c in codes if found.get((c, species_id))), None)


def prepare_game_payload(game, request=None) -> None:
    if game is None:
        return
    prefetch_related_objects([game], Prefetch('scores', queryset=_score_queryset()))
    scores = list(game.scores.all())

    highscore = game.current_highscore
    if highscore is not None:
        prefetch_related_objects([highscore], _answers_prefetch())
        scores.append(highscore)

    answers = [answer for score in scores for answer in score.answers.all()]
    if not answers:
        return
    languages = {game.language}
    if request is not None:
        languages.add(getattr(request, 'query_params', request.GET).get('language'))
    species = [a.question.species for a in answers] + [a.answer for a in answers]
    prime_species(species, languages)
    _prime_frequencies(answers)
