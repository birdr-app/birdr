# Game Lifecycle Documentation

This document describes the complete lifecycle of a game in the Motmot application, from creation to completion, including both single-player and multiplayer scenarios.

## Table of Contents

1. [Overview](#overview)
2. [Game Creation](#game-creation)
3. [Question Generation](#question-generation)
4. [Answer Submission](#answer-submission)
5. [Game Progression](#game-progression)
6. [Game Completion](#game-completion)
7. [Multiplayer Game Flow](#multiplayer-game-flow)
8. [WebSocket Communication](#websocket-communication)
9. [Rematch Functionality](#rematch-functionality)
10. [State Management](#state-management)

---

## Overview

A game in Motmot consists of:
- **Game**: The main entity containing game settings and metadata
- **Questions**: Individual quiz questions with species identification
- **Answers**: Player responses to questions
- **Player Scores**: Aggregated scores for multiplayer games

The game lifecycle follows these stages:
1. **Creation**: Game is created with specific settings
2. **Lobby** (multiplayer only): Players join and wait for host to start
3. **Question Loop**: Questions are generated and answered
4. **Completion**: Game ends when all questions are answered
5. **Results**: Scores are displayed and rematch option is available

---

## Game Creation

### Backend (Django)

#### Model: `Game` (`jizz/models.py`)

The `Game` model stores all game configuration:

```python
class Game(models.Model):
    token = ShortUUIDField(primary_key=True)  # Unique game identifier
    country = models.ForeignKey(Country)      # Country filter for species
    level = models.CharField()                 # 'beginner', 'intermediate', 'advanced'
    length = models.IntegerField()             # Number of questions
    media = models.CharField()                 # 'images', 'videos', 'sounds'
    host = models.ForeignKey(Player)           # Game creator (for multiplayer)
    multiplayer = models.BooleanField()         # Single or multiplayer
    include_rare = models.BooleanField()      # Include rare species
    include_escapes = models.BooleanField()    # Include escape species
    tax_order = models.CharField()            # Taxonomic order filter
    tax_family = models.CharField()           # Taxonomic family filter
    language = models.CharField()             # Language for species names
    repeat = models.BooleanField()            # Allow repeated species
    created = models.DateTimeField()          # Creation timestamp
    ended = models.BooleanField()             # Game completion status
```

#### API Endpoint: `POST /api/games/`

**View**: `GameListView` (`jizz/views.py`)

Creates a new game with the specified settings:

```python
# Request body
{
    "multiplayer": true,
    "country": "NL",
    "language": "en",
    "level": "advanced",
    "length": 10,
    "media": "images",
    "tax_order": null,
    "tax_family": null,
    "include_rare": true,
    "include_escapes": false
}
```

**Process**:
1. Validates player token from Authorization header
2. Creates `Game` instance with provided settings
3. Returns serialized game data including `token`

**Serializer**: `GameSerializer` (`jizz/serializers.py`)
- Handles nested `Country` serialization
- Validates game settings
- Returns game token for frontend use

### Frontend (React)

#### Component: `AppContextProvider` (`app/src/core/app-context-provider.tsx`)

**Function**: `createGame()`

```typescript
const createGame = async (myPlayer?: Player) => {
  // 1. Clear old game state
  localStorage.removeItem('game-token')
  setGame(undefined)  // Triggers WebSocket disconnection
  
  // 2. Wait for state to clear
  await new Promise(resolve => setTimeout(resolve, 0))
  
  // 3. Create new game via API
  const response = await fetch('/api/games/', {
    method: 'POST',
    headers: {
      'Authorization': `Token ${myPlayer.token}`
    },
    body: JSON.stringify({...gameSettings})
  })
  
  // 4. Store game token and update state
  const data = await response.json()
  localStorage.setItem('game-token', data.token)
  setGame(data)
  return data as Game
}
```

**Key Points**:
- Old game state is cleared before creating new game
- Game token is stored in `localStorage` for persistence
- Game state update triggers WebSocket connection (for multiplayer)

---

## Question Generation

### Backend

#### Method: `Game.add_question()` (`jizz/models.py`)

This method creates a new question for the game:

```python
def add_question(self):
    # 1. Mark all previous questions as done
    self.questions.filter(done=False).update(done=True)
    
    # 2. Calculate sequence number
    sequence = self.questions.count() + 1
    
    # 3. Check if game should end
    if sequence > self.length:
        self.ended = True
        self.save()
        return None
    
    # 4. Select random species based on filters
    species = self._select_species()
    
    # 5. Select random media item for the species
    media_count = self._get_media_count(species)
    number = randint(1, media_count) - 1
    
    # 6. Generate question with options based on level
    if self.level == 'advanced':
        # 5 options: 2 before, 2 after, 1 correct (by ID)
        options = self._get_advanced_options(species)
    elif self.level == 'beginner':
        # 4 options: 3 random + 1 correct
        options = self._get_beginner_options(species)
    else:
        # No options (free text input)
        options = []
    
    # 7. Create question and options
    question = self.questions.create(
        species=species,
        number=number,
        sequence=sequence
    )
    
    for index, option_species in enumerate(options):
        QuestionOption.objects.create(
            question=question,
            species=option_species,
            order=index
        )
    
    return question
```

#### Property: `Game.question` (`jizz/models.py`)

Returns the current active (undone) question:

```python
@property
def question(self):
    return self.questions.filter(done=False).first()
```

**Important**: This returns the first question where `done=False`, ensuring players always get the current question, not a completed one.

#### API Endpoint: `GET /api/games/{token}/question`

**View**: `QuestionView` (`jizz/views.py`)

```python
def get_object(self):
    game = Game.objects.get(token=self.kwargs["token"])
    if game.ended:
        raise NotFound("Game has ended")
    if not game.question:
        game.add_question()  # Generate if doesn't exist
    return game.question
```

**Process**:
1. Retrieves game by token
2. Checks if game has ended
3. Generates question if none exists
4. Returns current question via `QuestionSerializer`

**Serializer**: `QuestionSerializer` (`jizz/serializers.py`)

Includes:
- Question ID, number, sequence
- Species media (images, videos, sounds)
- Answer options (for multiple choice)
- **Game token** (for frontend validation)

```python
class QuestionSerializer(serializers.ModelSerializer):
    game = serializers.SerializerMethodField()
    
    def get_game(self, obj):
        return {'token': obj.game.token}  # Include for validation
```

---

## Answer Submission

### Backend

#### Model: `Answer` (`jizz/models.py`)

```python
class Answer(models.Model):
    question = models.ForeignKey(Question)
    player = models.ForeignKey(Player)
    answer = models.ForeignKey(Species, null=True)  # Selected species
    correct = models.BooleanField()                  # Auto-calculated
    created = models.DateTimeField()
```

#### API Endpoint: `POST /api/answers/`

**View**: `AnswerView` (`jizz/views.py`)

```python
def perform_create(self, serializer):
    answer = serializer.save()
    
    # Mark question as done
    answer.question.done = True
    answer.question.save()
    
    # Generate next question
    game = answer.question.game
    game.add_question()
```

**Process**:
1. Creates `Answer` instance
2. Marks question as `done=True`
3. Generates next question via `game.add_question()`
4. Returns answer with `correct` field calculated

**Serializer**: `AnswerSerializer` (`jizz/serializers.py`)

Validates:
- `player_token`: Must match authenticated player
- `question_id`: Must exist and belong to active game
- `answer_id`: Selected species (optional for free text)

Calculates `correct` by comparing `answer.species` with `question.species`.

### Frontend

#### WebSocket Action: `submit_answer`

**Component**: `WebsocketContextProvider` (`app/src/core/websocket-context-provider.tsx`)

```typescript
const submitAnswer = (answer: Answer) => {
  sendAction({
    action: 'submit_answer',
    player_token: answer.player?.token,
    question_id: answer.question?.id,
    answer_id: answer.answer?.id
  })
}
```

**Backend Handler**: `QuizConsumer.receive()` (`jizz/consumers.py`)

```python
elif data['action'] == 'submit_answer':
    # 1. Get player and question
    player = await sync_to_async(Player.objects.get)(token=data['player_token'])
    question = await sync_to_async(Question.objects.get)(id=data['question_id'])
    
    # 2. Create or update answer
    answer, created = await sync_to_async(Answer.objects.get_or_create)(
        question=question,
        player=player,
        defaults={'answer_id': data.get('answer_id')}
    )
    
    # 3. Calculate correctness
    answer.correct = (answer.answer == question.species)
    await sync_to_async(answer.save)()
    
    # 4. Mark question as done
    question.done = True
    await sync_to_async(question.save)()
    
    # 5. Send answer back to player
    await self.send(text_data=json.dumps({
        'action': 'answer_checked',
        'answer': AnswerSerializer(answer).data
    }))
    
    # 6. Update player scores
    await self.send_players_update(everyone=True)
    
    # 7. Generate next question if all players answered
    if await self.all_players_answered():
        await self.next_question()
```

---

## Game Progression

### Question Flow

1. **First Question**: Generated when game starts (via `start_game` action or first API call)
2. **Subsequent Questions**: Generated after all players submit answers
3. **Question Sequence**: Each question has a `sequence` number (1, 2, 3, ...)
4. **Game End**: When `sequence > game.length`, game is marked as `ended=True`

### Progress Tracking

**Property**: `Game.progress` (`jizz/models.py`)

```python
@property
def progress(self):
    return self.questions.count()  # Total questions created
```

**Frontend**: Progress is calculated as `questions.length / game.length`

### State Transitions

```
Game Created
    ↓
[Multiplayer] → Lobby (waiting for players)
    ↓
Game Started → First Question Generated
    ↓
Question Displayed → Players Answer
    ↓
All Players Answered → Next Question Generated
    ↓
[Repeat until sequence > length]
    ↓
Game Ended → Results Displayed
```

---

## Game Completion

### Backend

#### Game End Detection

In `Game.add_question()`:

```python
sequence = self.questions.count() + 1
if sequence > self.length:
    self.ended = True
    self.save()
    return None  # No more questions
```

#### Final Score Calculation

**Model**: `PlayerScore` (`jizz/models.py`)

```python
class PlayerScore(models.Model):
    game = models.ForeignKey(Game)
    player = models.ForeignKey(Player)
    score = models.IntegerField(default=0)
    
    @property
    def score(self):
        return self.answers.filter(correct=True).count()
```

**Serializer**: `PlayerScoreSerializer` (`jizz/serializers.py`)

Includes:
- Player name, language
- Total score (correct answers)
- Ranking (calculated by score, then by last answer time)
- All answers with correctness
- **is_host** flag (for rematch functionality)

### Frontend

#### Results Screen

**Component**: `Results` (`app/src/pages/mpg/play/results.tsx`)

Displays:
- Player rankings
- Individual scores
- Correct/incorrect answers
- **Rematch** button (host only)
- **Join rematch** button (other players)

---

## Multiplayer Game Flow

### WebSocket Connection

#### Connection Establishment

**Frontend**: `WebsocketContextProvider.connectSocket()`

```typescript
const connectSocket = (game: Game, player: Player) => {
  // 1. Clear old question/answer state
  setQuestion(undefined)
  setAnswer(undefined)
  
  // 2. Create WebSocket connection
  const ws = new WebSocket(`ws://127.0.0.1:8050/mpg/${game.token}`)
  
  // 3. Store game token on socket for validation
  (ws as any).gameToken = game.token
  
  // 4. On open: Join game
  ws.onopen = () => {
    ws.send(JSON.stringify({
      action: 'join_game',
      player_token: player.token,
      language_code: language
    }))
  }
  
  // 5. Handle messages
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data)
    // Validate game token before processing
    // ...
  }
}
```

#### Backend Consumer: `QuizConsumer` (`jizz/consumers.py`)

**Connection Handler**:

```python
async def connect(self):
    self.game_token = self.scope['url_route']['kwargs']['game_token']
    self.game_group_name = f'game_{self.game_token}'
    
    # Join game group
    await self.channel_layer.group_add(
        self.game_group_name,
        self.channel_name
    )
    
    await self.accept()
```

**Message Handler**:

```python
async def receive(self, text_data):
    data = json.loads(text_data)
    
    if data['action'] == 'join_game':
        # Add player to game
        # Send current players list
        await self.send_players_update(everyone=True)
        
    elif data['action'] == 'start_game':
        # Verify host
        # Generate first question
        # Send to all players
        await self.send_current_question(everyone=True)
        
    elif data['action'] == 'submit_answer':
        # Process answer
        # Update scores
        # Check if all answered
        if all_answered:
            await self.next_question()
            
    elif data['action'] == 'next_question':
        # Generate next question
        # Send to all players
        await self.send_current_question(everyone=True)
```

### Game State Synchronization

#### Player Updates

**Method**: `send_players_update()` (`jizz/consumers.py`)

```python
async def send_players_update(self, everyone):
    player_data = await self.get_player_data()
    if everyone:
        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'update_players', 'players': player_data}
        )
    else:
        await self.send(text_data=json.dumps({
            'action': 'update_players',
            'players': player_data
        }))
```

**Triggered**:
- When player joins
- After answer submission
- When game starts
- When question advances

#### Question Broadcasting

**Method**: `send_current_question()` (`jizz/consumers.py`)

```python
async def send_current_question(self, everyone):
    question = await self.get_current_question()
    if not question:
        return None
    
    serializer = QuestionSerializer(question)
    question_data = serializer.data
    
    # CRITICAL: Include game token for validation
    question_data['game'] = {'token': self.game_token}
    
    if everyone:
        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'new_question', 'question': question_data}
        )
    else:
        await self.send(text_data=json.dumps({
            'action': 'new_question',
            'question': question_data
        }))
```

**Frontend Validation**: All incoming questions are validated against current game token:

```typescript
// websocket-context-provider.tsx
case 'new_question':
  const question: Question = message.question
  const socketGameToken = (ws as any).gameToken
  const contextGameToken = getCurrentGameToken(game, gameToken)
  
  // Validate against both socket and context
  if (validateQuestionForGame(question, socketGameToken) && 
      validateQuestionForGame(question, contextGameToken)) {
    setQuestion(question)  // Only set if valid
  }
```

---

## Rematch Functionality

### Overview

Rematch allows players to start a new game with the same settings as the previous game, without manually re-entering all options.

### Backend

#### WebSocket Action: `rematch`

**Handler**: `QuizConsumer.receive()` (`jizz/consumers.py`)

```python
elif data['action'] == 'rematch':
    # 1. Verify player is host
    player = await sync_to_async(Player.objects.get)(token=data['player_token'])
    old_game = await sync_to_async(Game.objects.get)(token=self.game_token)
    
    if old_game.host != player:
        await self.send(text_data=json.dumps({
            'action': 'error',
            'message': 'Only the host can start a rematch'
        }))
        return
    
    # 2. Create new game with same settings
    new_game_token, host_name = await sync_to_async(create_rematch_game_sync)(
        data['player_token'], self.game_token
    )
    
    # 3. Send invitation to all players
    invitation_data = {
        'type': 'rematch_invitation',
        'new_game_token': new_game_token,
        'host_name': host_name
    }
    
    # Broadcast to all players
    await self.channel_layer.group_send(
        self.game_group_name,
        invitation_data
    )
    
    # Also send directly to requester
    await self.send(text_data=json.dumps({
        'action': 'rematch_invitation',
        'new_game_token': new_game_token,
        'host_name': host_name
    }))
```

#### Helper Function: `create_rematch_game_sync()`

```python
def create_rematch_game_sync(player_token, game_token):
    player = Player.objects.get(token=player_token)
    old_game = Game.objects.get(token=game_token)
    
    # Extract all settings from old game
    game_data = {
        'country': old_game.country,
        'level': old_game.level,
        'length': old_game.length,
        'media': old_game.media,
        'host': player,
        'multiplayer': old_game.multiplayer,
        'include_rare': old_game.include_rare,
        'include_escapes': old_game.include_escapes,
        'tax_order': old_game.tax_order,
        'tax_family': old_game.tax_family,
        'language': old_game.language,
        'repeat': old_game.repeat
    }
    
    # Create new game
    new_game = Game.objects.create(**game_data)
    return new_game.token, player.name
```

### Frontend

#### Rematch Handler

**Component**: `Results` (`app/src/pages/mpg/play/results.tsx`)

**Host Action**:

```typescript
const handleRematch = () => {
  // 1. Close old socket
  if (socket) {
    socket.close()
  }
  
  // 2. Clear old game state
  setGame(undefined)
  localStorage.removeItem('game-token')
  
  // 3. Send rematch request
  if (socket) {
    socket.send(JSON.stringify({
      action: 'rematch',
      player_token: player?.token
    }))
  }
  
  // 4. Wait for invitation (handled in useEffect)
}
```

**Host Auto-Join**:

```typescript
useEffect(() => {
  if (!isHost || !player) return
  
  const handleRematchInvitationForHost = (event: CustomEvent) => {
    const { new_game_token } = event.detail
    
    // Clear old state
    if (socket) socket.close()
    setGame(undefined)
    localStorage.removeItem('game-token')
    
    // Load new game
    setTimeout(async () => {
      const response = await fetch(`/api/games/${new_game_token}/`)
      const data = await response.json()
      
      setGame(data)
      localStorage.setItem('game-token', data.token)
      
      // Navigate to lobby
      setTimeout(() => {
        navigate('/game/lobby')
      }, 200)
    }, 200)
  }
  
  window.addEventListener('rematch_invitation', handleRematchInvitationForHost)
  return () => window.removeEventListener('rematch_invitation', handleRematchInvitationForHost)
}, [isHost, player, socket, setGame, navigate])
```

**Other Players**:

```typescript
const handleJoinRematch = () => {
  // Same process as host, but triggered manually via button
  // Button appears when rematch_invitation event is received
}
```

---

## State Management

### Frontend State Flow

#### Game Token Management

**Centralized Validator**: `game-token-validator.ts`

```typescript
// Validates questions belong to current game
export function validateQuestionForGame(
  question: Question | undefined,
  gameToken: string | undefined
): boolean

// Gets authoritative game token (context > localStorage)
export function getCurrentGameToken(
  contextGame: Game | undefined,
  localStorageToken: string | null
): string | undefined
```

**Custom Hook**: `use-game-token.ts`

```typescript
export function useGameToken() {
  return {
    currentGameToken: string | undefined,
    validateQuestion: (question: Question) => boolean,
    validateToken: (token: string) => boolean,
    hasGame: boolean
  }
}
```

#### State Clearing on Game Change

**WebSocket Context**: `websocket-context-provider.tsx`

```typescript
useEffect(() => {
  if (game?.token && game.token !== prevGameTokenRef.current) {
    // Game token changed - forget old game completely
    const oldToken = prevGameTokenRef.current
    
    // Close socket if it belongs to old game
    if (socket) {
      const socketGameToken = (socket as any).gameToken
      if (socketGameToken === oldToken) {
        socket.close()
        setSocket(undefined)
      }
    }
    
    // Clear all state
    setQuestion(undefined)
    setAnswer(undefined)
    setPlayers([])
    isConnectingRef.current = false
    retries.current = 0
    
    // Update ref
    prevGameTokenRef.current = game.token
  }
}, [game?.token, game, socket])
```

### Backend State

#### Game State Properties

- `game.ended`: Boolean indicating if game is complete
- `game.question`: Current active question (undone)
- `game.questions.count()`: Total questions created
- `game.progress`: Alias for `questions.count()`

#### Question State

- `question.done`: Boolean indicating if question is completed
- `question.sequence`: Question number in game (1, 2, 3, ...)
- `question.number`: Media item index for species

---

## Key Design Principles

### 1. Game Token Validation

**Always validate** that incoming data (questions, answers, game updates) belongs to the current game token. This prevents:
- Old questions from previous games appearing
- Answers being submitted to wrong games
- State corruption from stale data

### 2. State Isolation

**Completely clear** old game state when:
- Creating a new game
- Joining a rematch
- Game token changes

This ensures no data leaks between games.

### 3. WebSocket Connection Management

**One connection per game**: When game token changes, close old connection and establish new one.

**Connection validation**: Store game token on socket object and validate all incoming messages.

### 4. Question Generation

**Lazy generation**: Questions are generated on-demand, not all at once.

**Current question**: Always use `game.question` property (filters `done=False`) rather than `game.questions.last()`.

### 5. Multiplayer Synchronization

**Group messaging**: Use Django Channels group messaging for broadcasting to all players.

**State updates**: Send player updates after every significant action (join, answer, question advance).

---

## Testing

### Test Coverage

**File**: `jizz/tests.py`

Test classes:
- `GameLifecycleTestCase`: Single-player game flow
- `MultiplayerGameTestCase`: Multiplayer game scenarios
- `WebSocketConsumerTestCase`: WebSocket communication

**Key Test Scenarios**:
1. Game creation with various settings
2. Question generation and retrieval
3. Answer submission and scoring
4. Game completion detection
5. Multiplayer join/start flow
6. WebSocket message handling
7. Rematch functionality

---

## API Reference

### Game Endpoints

- `POST /api/games/` - Create game
- `GET /api/games/{token}/` - Get game details
- `GET /api/games/{token}/question` - Get current question
- `POST /api/answers/` - Submit answer

### WebSocket Actions

- `join_game` - Join multiplayer game
- `start_game` - Start game (host only)
- `submit_answer` - Submit answer to question
- `next_question` - Advance to next question
- `rematch` - Create rematch game (host only)

### WebSocket Events

- `update_players` - Player list updated
- `new_question` - New question available
- `answer_checked` - Answer processed
- `game_started` - Game has started
- `game_updated` - Game state changed
- `rematch_invitation` - Rematch game created

---

## Troubleshooting

### Common Issues

1. **Old questions appearing**: Ensure game token validation is working
2. **WebSocket reconnection loops**: Check `isConnectingRef` and connection state
3. **State not clearing**: Verify `useEffect` dependencies and state updates
4. **Rematch not working**: Check host verification and WebSocket message handling

### Debugging

- Check browser console for validation warnings
- Verify game token matches in all contexts
- Check WebSocket connection state
- Inspect `localStorage` for game token

---

## Future Enhancements

Potential improvements:
- Question caching for faster loading
- Offline game support
- Game replay functionality
- Advanced statistics and analytics
- Custom game modes


