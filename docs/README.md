# Motmot Game Documentation

This directory contains comprehensive documentation for the Motmot game application.

## Documentation Files

### [GAME_LIFECYCLE.md](./GAME_LIFECYCLE.md)
Complete documentation of the game lifecycle, including:
- Game creation and configuration
- Question generation and retrieval
- Answer submission and scoring
- Multiplayer game flow
- WebSocket communication
- Rematch functionality
- State management
- API reference
- Troubleshooting guide

## Quick Links

### Backend (Django)
- **Models**: `jizz/models.py` - Game, Question, Answer, Player models
- **Views**: `jizz/views.py` - REST API endpoints
- **Consumers**: `jizz/consumers.py` - WebSocket handlers
- **Serializers**: `jizz/serializers.py` - API serialization
- **Tests**: `jizz/tests.py` - Test suite

### Frontend (React/TypeScript)
- **App Context**: `app/src/core/app-context-provider.tsx` - Global state
- **WebSocket Context**: `app/src/core/websocket-context-provider.tsx` - WebSocket management
- **Game Token Validator**: `app/src/core/game-token-validator.ts` - Validation utilities
- **Game Token Hook**: `app/src/core/use-game-token.ts` - Custom hook for game token

## Key Concepts

### Game Token
Every game has a unique token that identifies it. This token is used to:
- Validate that questions/answers belong to the current game
- Manage WebSocket connections
- Prevent state leakage between games

### Question Generation
Questions are generated lazily (on-demand) when:
- Game starts (first question)
- All players submit answers (next question)
- Question is requested via API

### State Management
- **Backend**: Django models track game state
- **Frontend**: React Context API manages application state
- **WebSocket**: Real-time synchronization for multiplayer games

### Validation
All game-related data is validated against the current game token to prevent:
- Old questions from previous games
- Answers submitted to wrong games
- State corruption

## Getting Started

1. Read [GAME_LIFECYCLE.md](./GAME_LIFECYCLE.md) for complete understanding
2. Review test files in `jizz/tests.py` for usage examples
3. Check API endpoints in `jizz/views.py` for REST API details
4. Examine WebSocket handlers in `jizz/consumers.py` for real-time communication

## Contributing

When adding new features:
1. Update relevant documentation
2. Add tests to `jizz/tests.py`
3. Update API documentation if adding endpoints
4. Document WebSocket actions if adding new messages


