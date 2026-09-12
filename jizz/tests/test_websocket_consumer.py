import asyncio
import json
import unittest
from django.test import TransactionTestCase
from django.db import transaction
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from asgiref.sync import async_to_sync
from unittest.mock import AsyncMock, patch
from jizz.models import Game, Player, Answer, Species, Country, CountrySpecies, PlayerScore, UsageEvent
from media.models import Media
from jizz.asgi import application
from jizz.consumers import QuizConsumer


def _run_async(coro):
    """Run an async test coroutine under Django/Channels (Python 3.12-safe)."""
    async def _runner():
        return await coro

    return async_to_sync(_runner)()


class WebSocketConsumerTestCase(TransactionTestCase):
    """Test WebSocket consumer behavior for multiplayer games."""

    def setUp(self):
        """Set up test data for WebSocket tests."""
        # Create a country
        self.country, _create = Country.objects.get_or_create(
            code='NL',
            name='Netherlands'
        )

        # Create some species with media
        self.species_list = []
        for i in range(20):
            species = Species.objects.create(
                name=f'Species {i}',
                name_latin=f'Species Latin {i}',
                code=f'SP{i:03d}'
            )
            # Create country species relationship
            CountrySpecies.objects.create(
                country=self.country,
                species=species,
                status='native'
            )
            # Create media for each species
            Media.objects.create(
                species=species,
                type='image',
                url=f'https://example.com/image{i}.jpg',
                source='test'
            )
            self.species_list.append(species)

        # Create players
        self.player1 = Player.objects.create(
            name='Player 1',
            language='en'
        )
        self.player2 = Player.objects.create(
            name='Player 2',
            language='en'
        )

    def test_websocket_connect_and_join_game(self):
        """Test WebSocket connection and join_game action."""
        # Create game in sync test context (same DB connection as setUp)
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True
        )
        player1 = self.player1

        async def async_test():

            # Connect to WebSocket
            communicator = WebsocketCommunicator(
                application,
                f"/mpg/{game.token}"
            )
            connected, subprotocol = await communicator.connect()
            assert connected, "WebSocket connection failed"

            # Send join_game action
            await communicator.send_json_to({
                'action': 'join_game',
                'player_token': str(player1.token)
            })

            # Receive first message
            response = await communicator.receive_json_from(timeout=2.0)
            assert 'action' in response
            actions_received = [response.get('action')]
            # Collect any further messages (player_joined, update_players, game_updated)
            try:
                while True:
                    response = await communicator.receive_json_from(timeout=1.0)
                    actions_received.append(response.get('action'))
            except Exception:
                pass  # Timeout or disconnect when no more messages

            # Verify we received expected actions (join sends player_joined, update_players, and game_updated)
            assert 'player_joined' in actions_received, f"Expected player_joined, got {actions_received}"
            assert 'update_players' in actions_received, f"Expected update_players, got {actions_received}"
            assert 'game_updated' in actions_received, f"Expected game_updated, got {actions_received}"
            assert 'game_started' not in actions_received, f"Lobby join before start must not send game_started, got {actions_received}"
            assert 'new_question' not in actions_received, f"Lobby join before start must not send new_question, got {actions_received}"

            # Clean up
            await communicator.disconnect()

        _run_async(async_test())
        score = PlayerScore.objects.get(player=player1, game=game)
        self.assertEqual(score.app_version, '')
        self.assertEqual(score.device_type, '')

    def test_join_game_stores_optional_app_version_and_device_type(self):
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )
        player1 = self.player1

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({
                'action': 'join_game',
                'player_token': str(player1.token),
                'app_version': '2.0.1',
                'device_type': 'android',
            })
            try:
                while True:
                    await communicator.receive_json_from(timeout=1.0)
            except Exception:
                pass
            await communicator.disconnect()

        _run_async(async_test())
        score = PlayerScore.objects.get(player=player1, game=game)
        self.assertEqual(score.app_version, '2.0.1')
        self.assertEqual(score.device_type, 'android')
        event = UsageEvent.objects.filter(event_type='websocket', path='Joined game lobby').latest('created_at')
        self.assertEqual(event.app_version, '2.0.1')
        self.assertEqual(event.platform, 'android')
        self.assertEqual(event.device_type, 'mobile')

    def test_join_game_after_start_resyncs_current_question(self):
        """Reconnect after start must get game_started + the active question (Android Lobby→Play)."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )
        PlayerScore.objects.get_or_create(player=self.player1, game=game)
        question = game.add_question()
        transaction.commit()

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({
                'action': 'join_game',
                'player_token': str(self.player1.token),
            })
            actions = []
            question_msg = None
            try:
                while True:
                    msg = await communicator.receive_json_from(timeout=5.0)
                    actions.append(msg.get('action'))
                    if msg.get('action') == 'new_question':
                        question_msg = msg
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError, Exception):
                pass
            self.assertIn('game_updated', actions, f'got {actions}')
            self.assertIn('game_started', actions, f'got {actions}')
            self.assertIn('new_question', actions, f'got {actions}')
            self.assertIsNotNone(question_msg)
            self.assertEqual(question_msg['question']['id'], question.id)
            self.assertEqual(
                str(question_msg['question']['game']['token']),
                str(game.token),
            )
            await communicator.disconnect()

        _run_async(async_test())

    def test_websocket_disconnect(self):
        """Test that connect then disconnect runs without error."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

        _run_async(async_test())

    def test_websocket_receive_invalid_json_no_crash(self):
        """Test that invalid JSON in receive() does not raise."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_to(text_data="not valid json")
            # Consumer should not raise; no response expected for invalid JSON
            await communicator.disconnect()

        _run_async(async_test())

    def test_websocket_receive_unknown_action_no_crash(self):
        """Test that unknown action in receive() does not raise."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({"action": "unknown_action"})
            # Consumer should not raise
            await communicator.disconnect()

        _run_async(async_test())

    @unittest.skip("WebSocket rematch with DB: consumer runs in async thread; DB visibility can prevent response in CI")
    def test_websocket_rematch_as_host_returns_invitation(self):
        """Test that rematch action by host sends rematch_invitation with new_game_token."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )
        PlayerScore.objects.get_or_create(player=self.player1, game=game)
        host = self.player1
        # Force commit so the rematch sync thread (database_sync_to_async) sees the game
        transaction.commit()

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({
                'action': 'join_game',
                'player_token': str(host.token),
            })
            # Drain join messages
            try:
                while True:
                    await communicator.receive_json_from(timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
                pass
            await communicator.send_json_to({
                'action': 'rematch',
                'player_token': str(host.token),
            })
            try:
                msg = await communicator.receive_json_from(timeout=15.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError) as e:
                self.fail(f"Rematch did not receive response within 15s: {e}")
            self.assertEqual(msg.get('action'), 'rematch_invitation', f"Expected rematch_invitation, got {msg}")
            self.assertIn('new_game_token', msg)
            self.assertIn('host_name', msg)
            self.assertNotEqual(msg['new_game_token'], game.token)
            await communicator.disconnect()

        _run_async(async_test())

    @unittest.skip("WebSocket rematch with DB: consumer runs in async thread; DB visibility can prevent response in CI")
    def test_websocket_rematch_as_non_host_returns_error(self):
        """Test that rematch action by non-host sends error action."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )
        PlayerScore.objects.get_or_create(player=self.player1, game=game)
        PlayerScore.objects.get_or_create(player=self.player2, game=game)
        transaction.commit()

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({
                'action': 'join_game',
                'player_token': str(self.player2.token),
            })
            try:
                while True:
                    await communicator.receive_json_from(timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
                pass
            await communicator.send_json_to({
                'action': 'rematch',
                'player_token': str(self.player2.token),
            })
            try:
                msg = await communicator.receive_json_from(timeout=15.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError) as e:
                self.fail(f"Rematch did not receive response within 15s: {e}")
            self.assertEqual(msg.get('action'), 'error', f"Expected error, got {msg}")
            self.assertIn('message', msg)
            self.assertIn('host', msg['message'].lower())
            await communicator.disconnect()

        _run_async(async_test())

    def test_websocket_rematch_without_player_token_returns_error(self):
        """Test that rematch without player_token sends error."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({'action': 'rematch'})
            msg = await communicator.receive_json_from(timeout=5.0)
            self.assertEqual(msg.get('action'), 'error')
            self.assertIn('player_token', msg.get('message', ''))
            await communicator.disconnect()

        _run_async(async_test())

    @unittest.skip("start_game/add_question in consumer run in thread pool; test DB visibility can cause timeouts")
    def test_websocket_start_game_sends_question(self):
        """Test that start_game action sends a question to all players."""
        # Create game and player scores in sync test context (same DB connection as setUp)
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True
        )
        PlayerScore.objects.get_or_create(player=self.player1, game=game)
        PlayerScore.objects.get_or_create(player=self.player2, game=game)

        async def async_test():

            # Connect player 1
            communicator1 = WebsocketCommunicator(
                application,
                f"/mpg/{game.token}"
            )
            connected, _ = await communicator1.connect()
            assert connected, "WebSocket connection failed"

            # Join game
            await communicator1.send_json_to({
                'action': 'join_game',
                'player_token': str(self.player1.token)
            })

            # Clear initial messages (join sends several)
            try:
                while True:
                    await communicator1.receive_json_from(timeout=2.0)
            except (Exception, asyncio.CancelledError, asyncio.TimeoutError):
                pass

            # Start game
            await communicator1.send_json_to({
                'action': 'start_game'
            })

            # Should receive game_started and new_question (receive can raise CancelledError on timeout)
            messages = []
            try:
                while len(messages) < 2:
                    response = await communicator1.receive_json_from(timeout=10.0)
                    messages.append(response)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
                pass

            # Verify we got game_started and new_question
            actions = [msg.get('action') for msg in messages]
            assert 'game_started' in actions, f"Expected game_started, got {actions}"
            assert 'new_question' in actions, f"Expected new_question, got {actions}"

            # Verify question data structure
            question_msg = next((msg for msg in messages if msg.get('action') == 'new_question'), None)
            assert question_msg is not None, "No new_question message received"
            assert 'question' in question_msg
            assert 'game' in question_msg['question']
            assert question_msg['question']['game']['token'] == game.token

            await communicator1.disconnect()

        _run_async(async_test())

    @unittest.skip("start_game/add_question in consumer run in thread pool; test DB visibility can cause timeouts")
    def test_websocket_multiple_players_receive_question(self):
        """Test that multiple players connected via WebSocket receive questions."""
        # Create game and player scores in sync test context (same DB connection as setUp)
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True
        )
        PlayerScore.objects.get_or_create(player=self.player1, game=game)
        PlayerScore.objects.get_or_create(player=self.player2, game=game)
        player1 = self.player1
        player2 = self.player2

        async def async_test():

            # Connect both players
            communicator1 = WebsocketCommunicator(
                application,
                f"/mpg/{game.token}"
            )
            communicator2 = WebsocketCommunicator(
                application,
                f"/mpg/{game.token}"
            )

            connected1, _ = await communicator1.connect()
            connected2, _ = await communicator2.connect()
            assert connected1, "Player 1 WebSocket connection failed"
            assert connected2, "Player 2 WebSocket connection failed"

            # Both players join
            await communicator1.send_json_to({
                'action': 'join_game',
                'player_token': str(player1.token)
            })
            await communicator2.send_json_to({
                'action': 'join_game',
                'player_token': str(player2.token)
            })

            # Clear initial messages (join sends several per connection)
            for comm in [communicator1, communicator2]:
                try:
                    while True:
                        await comm.receive_json_from(timeout=2.0)
                except (Exception, asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            # Player 1 starts game
            await communicator1.send_json_to({
                'action': 'start_game'
            })

            # Both players should receive game_started and new_question (receive can raise CancelledError on timeout)
            for comm in [communicator1, communicator2]:
                messages = []
                try:
                    while len(messages) < 2:
                        response = await comm.receive_json_from(timeout=10.0)
                        messages.append(response)
                except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
                    pass

                actions = [msg.get('action') for msg in messages]
                assert 'game_started' in actions, f"Expected game_started, got {actions}"
                assert 'new_question' in actions, f"Expected new_question, got {actions}"

                # Verify question has game token
                question_msg = next((msg for msg in messages if msg.get('action') == 'new_question'), None)
                assert question_msg is not None, "No new_question message received"
                assert question_msg['question']['game']['token'] == game.token

            await communicator1.disconnect()
            await communicator2.disconnect()

        _run_async(async_test())

    @unittest.skip("submit_answer in consumer runs in thread pool; test DB visibility can cause timeouts")
    def test_websocket_submit_answer(self):
        """Test submitting an answer via WebSocket."""
        # Create game, player score and question in sync test context (same DB connection as setUp)
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True
        )
        player_score, _ = PlayerScore.objects.get_or_create(player=self.player1, game=game)
        question = game.add_question()
        player1 = self.player1

        async def async_test():

            # Connect and join
            communicator = WebsocketCommunicator(
                application,
                f"/mpg/{game.token}"
            )
            connected, _ = await communicator.connect()
            assert connected, "WebSocket connection failed"

            await communicator.send_json_to({
                'action': 'join_game',
                'player_token': str(player1.token)
            })

            # Clear initial messages (join sends several)
            try:
                while True:
                    await communicator.receive_json_from(timeout=2.0)
            except (Exception, asyncio.CancelledError, asyncio.TimeoutError):
                pass

            # Submit answer
            await communicator.send_json_to({
                'action': 'submit_answer',
                'player_token': str(player1.token),
                'question_id': question.id,
                'answer_id': question.species.id
            })

            # Should receive answer_checked and update_players (receive can raise CancelledError on timeout)
            messages = []
            try:
                while len(messages) < 2:
                    response = await communicator.receive_json_from(timeout=10.0)
                    messages.append(response)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
                pass

            actions = [msg.get('action') for msg in messages]
            assert 'answer_checked' in actions, f"Expected answer_checked, got {actions}"
            assert 'update_players' in actions, f"Expected update_players, got {actions}"

            # Verify answer was created
            answer = await database_sync_to_async(
                lambda: Answer.objects.filter(
                    player_score=player_score,
                    question=question
                ).first()
            )()
            assert answer is not None, "Answer was not created"
            assert answer.correct, "Answer should be correct"

            await communicator.disconnect()

        _run_async(async_test())

    @unittest.skip("next_question/add_question in consumer run in thread pool; test DB visibility can cause timeouts")
    def test_websocket_next_question(self):
        """Test next_question action via WebSocket."""
        # Create game and player score in sync test context (same DB connection as setUp)
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True
        )
        PlayerScore.objects.get_or_create(player=self.player1, game=game)
        player1 = self.player1

        async def async_test():

            # Connect and join
            communicator = WebsocketCommunicator(
                application,
                f"/mpg/{game.token}"
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({
                'action': 'join_game',
                'player_token': str(player1.token)
            })

            # Clear initial messages (join sends several)
            try:
                while True:
                    await communicator.receive_json_from(timeout=2.0)
            except (Exception, asyncio.CancelledError, asyncio.TimeoutError):
                pass

            # Start game to get first question
            await communicator.send_json_to({
                'action': 'start_game'
            })

            # Clear start game messages (game_started, new_question)
            try:
                while True:
                    await communicator.receive_json_from(timeout=2.0)
            except (Exception, asyncio.CancelledError, asyncio.TimeoutError):
                pass

            # Request next question
            await communicator.send_json_to({
                'action': 'next_question'
            })

            # Should receive new_question (receive can raise CancelledError on timeout)
            try:
                response = await communicator.receive_json_from(timeout=10.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, TimeoutError):
                self.fail("Did not receive new_question within timeout")
            self.assertEqual(response.get('action'), 'new_question')
            self.assertIn('question', response)
            self.assertEqual(response['question']['game']['token'], game.token)

            await communicator.disconnect()

        _run_async(async_test())

    def test_receive_missing_action_no_crash(self):
        """Receive with empty object or missing 'action' does not raise."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )

        async def async_test():
            communicator = WebsocketCommunicator(application, f"/mpg/{game.token}")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({})
            await communicator.send_json_to({"other_key": "value"})
            # No response expected; disconnect without error
            await communicator.disconnect()

        _run_async(async_test())

    def test_websocket_connect_invalid_game_token_accepts(self):
        """Connect with a game token that does not exist in DB still accepts (game loaded later on join)."""
        async def async_test():
            communicator = WebsocketCommunicator(application, "/mpg/nonexistent-token-xyz")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

        _run_async(async_test())

    def test_channel_handler_update_players_sends_correct_json(self):
        """Group handler update_players sends action and players to client."""
        async def async_test():
            consumer = QuizConsumer()
            consumer.send = AsyncMock()
            await consumer.update_players({'players': [{'name': 'P1', 'score': 10}]})
            consumer.send.assert_called_once()
            payload = json.loads(consumer.send.call_args[1]['text_data'])
            self.assertEqual(payload['action'], 'update_players')
            self.assertEqual(payload['players'], [{'name': 'P1', 'score': 10}])

        _run_async(async_test())

    def test_channel_handler_player_joined_sends_correct_json(self):
        """Group handler player_joined sends action and player_name."""
        async def async_test():
            consumer = QuizConsumer()
            consumer.send = AsyncMock()
            await consumer.player_joined({'player_name': 'Alice'})
            consumer.send.assert_called_once()
            payload = json.loads(consumer.send.call_args[1]['text_data'])
            self.assertEqual(payload['action'], 'player_joined')
            self.assertEqual(payload['player_name'], 'Alice')

        _run_async(async_test())

    def test_channel_handler_game_started_sends_correct_json(self):
        """Group handler game_started sends action (and tries to push current question)."""
        async def async_test():
            consumer = QuizConsumer()
            consumer.send = AsyncMock()
            consumer._send_current_question_to_self = AsyncMock()
            await consumer.game_started({})
            consumer.send.assert_called_once()
            payload = json.loads(consumer.send.call_args[1]['text_data'])
            self.assertEqual(payload['action'], 'game_started')
            consumer._send_current_question_to_self.assert_awaited_once()

        _run_async(async_test())

    def test_channel_handler_new_question_sends_correct_json(self):
        """Group handler new_question sends action and question."""
        async def async_test():
            consumer = QuizConsumer()
            consumer.send = AsyncMock()
            question_data = {'id': 1, 'species': 1}
            await consumer.new_question({'question': question_data})
            consumer.send.assert_called_once()
            payload = json.loads(consumer.send.call_args[1]['text_data'])
            self.assertEqual(payload['action'], 'new_question')
            self.assertEqual(payload['question'], question_data)

        _run_async(async_test())

    def test_channel_handler_rematch_invitation_sends_correct_json(self):
        """Group handler rematch_invitation sends action, new_game_token, host_name."""
        async def async_test():
            consumer = QuizConsumer()
            consumer.send = AsyncMock()
            await consumer.rematch_invitation({
                'new_game_token': 'abc123',
                'host_name': 'Host',
            })
            consumer.send.assert_called_once()
            payload = json.loads(consumer.send.call_args[1]['text_data'])
            self.assertEqual(payload['action'], 'rematch_invitation')
            self.assertEqual(payload['new_game_token'], 'abc123')
            self.assertEqual(payload['host_name'], 'Host')

        _run_async(async_test())

    def test_websocket_end_game_broadcasts_game_ended(self):
        """end_game force-ends the game and sends game_ended to the caller."""
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player1,
            multiplayer=True,
        )
        PlayerScore.objects.get_or_create(player=self.player1, game=game)
        transaction.commit()

        async def async_test():
            consumer = QuizConsumer()
            consumer.game_token = game.token
            consumer.game_group_name = f'quiz_{game.token}'
            consumer.channel_layer = AsyncMock()
            consumer.channel_layer.group_send = AsyncMock()
            consumer.send = AsyncMock()
            consumer.scope = {}
            consumer._log_websocket_action = AsyncMock()

            await consumer._handle_end_game({
                'player_token': str(self.player1.token),
            })

            consumer.channel_layer.group_send.assert_awaited()
            args = consumer.channel_layer.group_send.await_args
            self.assertEqual(args.args[0], consumer.game_group_name)
            self.assertEqual(args.args[1]['type'], 'mpg_game_ended')
            self.assertTrue(args.args[1]['game'].get('ended'))

            # Also exercise the client fan-out handler.
            consumer.send.reset_mock()
            await consumer.mpg_game_ended({'game': args.args[1]['game']})
            payload = json.loads(consumer.send.call_args[1]['text_data'])
            self.assertEqual(payload['action'], 'game_ended')

        _run_async(async_test())

        game.refresh_from_db()
        self.assertTrue(game.force_ended)
