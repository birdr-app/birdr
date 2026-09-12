"""
Multiplayer quiz WebSocket consumer (Django Channels).

URL: ws(s)://<host>/mpg/<game_token>
Each connection is scoped to one game group `quiz_<game_token>`.

Client -> server actions: join_game, start_game, next_question, submit_answer, rematch, end_game.
Server -> client: update_players, new_question, game_started, game_updated, game_ended, answer_checked, etc.

All ORM / serializer work runs inside ``database_sync_to_async`` helpers so Django never
raises SynchronousOnlyOperation in the async consumer (e.g. reconnect join_game on results).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from jizz.usage_analytics import record_websocket_usage_event

logger = logging.getLogger(__name__)


def _as_int(value, field_name: str):
    """Coerce JSON number or numeric string for ORM / comparisons."""
    if value is None:
        raise ValueError(f"missing {field_name}")
    if isinstance(value, bool):
        raise ValueError(f"invalid {field_name}")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid {field_name}") from e


class QuizConsumer(AsyncWebsocketConsumer):
    """
    One consumer instance per WebSocket connection.
    All per-connection state must live on self (never rely on class attributes for instance data).
    """

    async def connect(self):
        self.game_token = self.scope["url_route"]["kwargs"]["game_token"]
        self.game_group_name = f"quiz_{self.game_token}"
        # Player token from the last join_game on this connection (for send_current_answer)
        self._player_token: Optional[str] = None
        self._app_identity: dict = {}
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        self._player_token = None
        self._app_identity = {}
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError as e:
            logger.warning("WebSocket JSON parse error: %s data=%s", e, text_data[:200])
            return

        action = data.get("action")
        if not action:
            return

        try:
            if action == "join_game":
                await self._handle_join_game(data)
            elif action == "start_game":
                await self._handle_start_game(data)
            elif action == "next_question":
                await self._handle_next_question(data)
            elif action == "submit_answer":
                await self._handle_submit_answer(data)
            elif action == "rematch":
                await self._handle_rematch(data)
            elif action == "end_game":
                await self._handle_end_game(data)
        except Exception as e:
            logger.exception("WebSocket action %s failed: %s", action, e)
            await self.send(
                text_data=json.dumps(
                    {"action": "error", "message": str(e) or "Server error"}
                )
            )

    async def _log_websocket_action(self, action: str):
        try:
            identity = getattr(self, '_app_identity', None) or {}
            await database_sync_to_async(record_websocket_usage_event)(
                self.scope,
                action=action,
                metadata={'game_token': self.game_token},
                app_version=identity.get('app_version', ''),
                app_build=identity.get('app_build', ''),
                os_version=identity.get('os_version', ''),
                platform=identity.get('platform', ''),
            )
        except Exception:
            logger.exception("Failed to record websocket usage for %s", action)

    # --- Handlers ---

    async def _handle_end_game(self, data):
        """Any player in the game may end the session: finished games broadcast as-is; otherwise force end."""
        from django.core.exceptions import ObjectDoesNotExist

        from .models import Game, Player, PlayerScore
        from .serializers import GameSerializer

        player_token = (data.get("player_token") or "").strip()
        if not player_token:
            await self.send(
                text_data=json.dumps(
                    {"action": "error", "message": "player_token required"}
                )
            )
            return

        def load_game_and_payload():
            game = Game.objects.select_related("host", "country").get(
                token=self.game_token
            )
            player = Player.objects.get(token=player_token)
            PlayerScore.objects.get(player=player, game=game)
            if not game.ended:
                # Close any in-progress question so current-question APIs are consistent.
                game.questions.filter(done=False).update(done=True)
                if not game.ended:
                    game.force_ended = True
                    game.save(update_fields=["force_ended"])
            return GameSerializer(game).data

        try:
            game_data = await database_sync_to_async(load_game_and_payload)()
        except ObjectDoesNotExist:
            await self.send(
                text_data=json.dumps(
                    {"action": "error", "message": "Game or player not found"}
                )
            )
            return
        except ValueError as e:
            await self.send(
                text_data=json.dumps({"action": "error", "message": str(e)})
            )
            return

        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "mpg_game_ended", "game": game_data},
        )
        await self._log_websocket_action("end_game")

    async def _handle_join_game(self, data):
        from django.core.exceptions import ObjectDoesNotExist

        from jizz.models import Game, Player

        player_token = (data.get("player_token") or "").strip()
        if not player_token:
            await self.send(
                text_data=json.dumps(
                    {"action": "error", "message": "player_token required"}
                )
            )
            return

        def do_join():
            game = Game.objects.get(token=self.game_token)
            player = Player.objects.get(token=player_token)
            from jizz.client_info import client_info_from_mapping, record_player_score_client
            from jizz.usage_analytics import app_identity_from_mapping

            self._app_identity = app_identity_from_mapping(data)
            app_version, device_type = client_info_from_mapping(data)
            record_player_score_client(player, game, app_version, device_type)
            current = game.question
            return (
                player.name,
                bool(game.ended),
                current.id if current else None,
            )

        try:
            player_name, game_ended, current_question_id = await database_sync_to_async(
                do_join
            )()
        except ObjectDoesNotExist:
            await self.send(
                text_data=json.dumps(
                    {"action": "error", "message": "Game or player not found"}
                )
            )
            return

        self._player_token = player_token
        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "player_joined", "player_name": player_name},
        )
        await self._broadcast_players_update()
        await self._send_game_update_to_self()
        # Reconnecting clients (Android Lobby → GamePlay) missed the original
        # game_started / new_question on the dead lobby socket. Always resync
        # the active round to this connection.
        if not game_ended and current_question_id:
            await self.send(text_data=json.dumps({"action": "game_started"}))
            await self._send_question_to_self(current_question_id)
            await self._send_current_answer_to_self()
        await self._log_websocket_action("join_game")

    async def _handle_start_game(self, data):
        from .models import Game

        def prepare_start():
            game = Game.objects.get(token=self.game_token)
            return game.can_accept_start_game()

        should_run = await database_sync_to_async(prepare_start)()
        if not should_run:
            logger.info(
                "Ignoring duplicate start_game for game %s",
                self.game_token,
            )
            return

        # Create/activate the first question before game_started so joiners and HTTP
        # catch-up see an active round (game_started handlers call _send_current_question_to_self).
        await self._run_next_question()
        await self.send(text_data=json.dumps({"action": "game_started"}))
        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "game_started"},
        )
        await self._log_websocket_action("start_game")

    async def _handle_next_question(self, data):
        from .models import Game

        def can_advance():
            game = Game.objects.get(token=self.game_token)
            return game.can_advance_to_next_question()

        if not await database_sync_to_async(can_advance)():
            logger.info(
                "Ignoring next_question for game %s (host has not answered current round)",
                self.game_token,
            )
            return
        await self._run_next_question()
        await self._log_websocket_action("next_question")

    async def _handle_submit_answer(self, data):
        try:
            player_token = (data.get("player_token") or "").strip()
            question_id = _as_int(data.get("question_id"), "question_id")
            answer_id = _as_int(data.get("answer_id"), "answer_id")
        except ValueError as e:
            await self.send(
                text_data=json.dumps({"action": "error", "message": str(e)})
            )
            return

        if not player_token:
            await self.send(
                text_data=json.dumps(
                    {"action": "error", "message": "player_token required"}
                )
            )
            return

        def submit_and_serialize():
            from jizz.models import PlayerScore, Player, Question, Answer, Game
            from jizz.serializers import AnswerSerializer
            from jizz.services.checklist import (
                compute_checklist_added,
                compute_checklist_missed,
            )

            player = Player.objects.select_related('user').get(token=player_token)
            game = Game.objects.get(token=self.game_token)
            player_score = PlayerScore.objects.get(player=player, game=game)
            question = Question.objects.select_related('game__country', 'species').get(
                id=question_id
            )

            if question.game_id != game.id:
                raise ValueError("Question does not belong to this game")

            correct = answer_id == question.species_id

            qs = Answer.objects.select_related(
                'question__game__country',
                'question__species',
                'answer',
            )
            row = qs.filter(player_score=player_score, question=question).first()
            if row:
                row.checklist_added = False
                row.checklist_missed = False
            else:
                row = Answer.objects.create(
                    answer_id=answer_id,
                    player_score=player_score,
                    question=question,
                    correct=correct,
                )
                checklist_user = player.user if player.user_id else None
                row.checklist_added = compute_checklist_added(
                    player, question, correct, user=checklist_user
                )
                row.checklist_missed = compute_checklist_missed(
                    player, question, correct, user=checklist_user
                )

            serializer = AnswerSerializer(
                row, context={"game": game, "include_media_link": True}
            )
            return serializer.data

        try:
            answer_data = await database_sync_to_async(submit_and_serialize)()
        except ValueError as e:
            await self.send(
                text_data=json.dumps({"action": "error", "message": str(e)})
            )
            return

        await self.send(
            text_data=json.dumps({"action": "answer_checked", "answer": answer_data})
        )

        await self._broadcast_players_update()
        await self._log_websocket_action("submit_answer")

    async def _handle_rematch(self, data):
        player_token = (data.get("player_token") or "").strip()
        if not player_token:
            await self.send(
                text_data=json.dumps(
                    {"action": "error", "message": "player_token is required for rematch"}
                )
            )
            return
        try:
            from jizz.rematch import create_rematch_game as do_create_rematch

            def run_rematch():
                new_game, player = do_create_rematch(self.game_token, player_token)
                return new_game.token, player.name

            new_game_token, player_name = await database_sync_to_async(run_rematch)()
            invitation_data = {
                "type": "rematch_invitation",
                "new_game_token": new_game_token,
                "host_name": player_name,
            }
            await self.channel_layer.group_send(self.game_group_name, invitation_data)
            await self.send(
                text_data=json.dumps(
                    {
                        "action": "rematch_invitation",
                        "new_game_token": new_game_token,
                        "host_name": player_name,
                    }
                )
            )
            await self._log_websocket_action("rematch")
        except Exception as e:
            logger.exception("rematch failed")
            await self.send(
                text_data=json.dumps(
                    {
                        "action": "error",
                        "message": f"Failed to create rematch: {str(e)}",
                    }
                )
            )

    # --- Game flow helpers ---

    async def _run_next_question(self):
        from .models import Game

        def advance():
            game = Game.objects.get(token=self.game_token)
            return game.add_question()

        question = await database_sync_to_async(advance)()
        if question:
            await self._broadcast_question_payload(question.id)
        else:
            await self._broadcast_current_question()

    async def _broadcast_players_update(self):
        player_data = await self._get_player_data()
        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "update_players", "players": player_data},
        )

    async def _get_player_data(self):
        from .models import Game
        from .serializers import PlayerScoreSerializer

        def get_data():
            game = Game.objects.get(token=self.game_token)
            scores = list(
                game.scores.select_related('player', 'game__country').order_by('-score')
            )
            return PlayerScoreSerializer(scores, many=True).data

        return await database_sync_to_async(get_data)()

    async def _send_game_update_to_self(self):
        from .models import Game
        from .serializers import GameSerializer

        def get_game_data():
            g = Game.objects.select_related('host', 'country').get(token=self.game_token)
            return GameSerializer(g).data

        game_data = await database_sync_to_async(get_game_data)()
        await self.send(
            text_data=json.dumps({"action": "game_updated", "game": game_data})
        )

    async def _current_question_id(self) -> Optional[int]:
        from .models import Game

        def get_id():
            game = Game.objects.get(token=self.game_token)
            question = game.question
            return question.id if question else None

        return await database_sync_to_async(get_id)()

    async def _send_current_question_to_self(self):
        question_id = await self._current_question_id()
        await self._send_question_to_self(question_id)

    async def _send_question_to_self(self, question_id: Optional[int]):
        if not question_id:
            return
        q = await self._serialize_question_for_send(question_id)
        if not q:
            return
        await self.send(
            text_data=json.dumps({"action": "new_question", "question": q})
        )

    async def _broadcast_current_question(self):
        q = await self._serialize_current_question_for_send()
        if not q:
            return
        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "new_question", "question": q},
        )

    async def _broadcast_question_payload(self, question_id: int):
        q = await self._serialize_question_for_send(question_id)
        if not q:
            return
        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "new_question", "question": q},
        )

    async def _serialize_current_question_for_send(self):
        question_id = await self._current_question_id()
        if not question_id:
            return None
        return await self._serialize_question_for_send(question_id)

    async def _serialize_question_for_send(self, question_id: int):
        from .question_play import load_question_for_play, serialize_question_for_play

        def _build_payload():
            q = load_question_for_play(question_id)
            data = serialize_question_for_play(q)
            data["game"] = {"token": str(q.game.token)}
            return data

        return await database_sync_to_async(_build_payload)()

    async def _send_current_answer_to_self(self):
        if not self._player_token:
            return

        def load_answer_payload():
            from jizz.models import Player, Answer
            from jizz.serializers import AnswerSerializer
            from .models import Game

            game = Game.objects.get(token=self.game_token)
            question = game.question
            if not question:
                return None
            player = Player.objects.get(token=self._player_token)
            answer = Answer.objects.filter(
                player_score__player=player, question=question
            ).select_related(
                'question__game__country',
                'question__species',
                'answer',
            ).first()
            if not answer:
                return None
            serializer = AnswerSerializer(
                answer, context={"game": game, "include_media_link": True}
            )
            return serializer.data

        data = await database_sync_to_async(load_answer_payload)()
        if not data:
            return
        await self.send(
            text_data=json.dumps({"action": "answer_checked", "answer": data})
        )

    # --- Channel layer event handlers (type = snake_case method name) ---

    async def update_players(self, event):
        await self.send(
            text_data=json.dumps(
                {"action": "update_players", "players": event["players"]}
            )
        )

    async def player_joined(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "action": "player_joined",
                    "player_name": event["player_name"],
                }
            )
        )

    async def game_started(self, event):
        await self.send(text_data=json.dumps({"action": "game_started"}))
        # Direct follow-up: group new_question can race with connect/join on mobile clients.
        await self._send_current_question_to_self()

    async def new_question(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "action": "new_question",
                    "question": event["question"],
                }
            )
        )

    async def player_answered(self, event):
        await self.send(
            text_data=json.dumps(
                {"action": "player_answered", "player": event["player"]}
            )
        )

    async def rematch_invitation(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "action": "rematch_invitation",
                    "new_game_token": event["new_game_token"],
                    "host_name": event["host_name"],
                }
            )
        )

    async def mpg_game_ended(self, event):
        await self.send(
            text_data=json.dumps(
                {"action": "game_ended", "game": event["game"]}
            )
        )
