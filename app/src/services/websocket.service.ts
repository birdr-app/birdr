// WebSocket Service - Handles WebSocket connections with reconnection logic
import { Game, Player, MultiPlayer, Question, Answer } from '../api/types';
import { clientInfoPayload } from '../api/clientInfo';

export interface WebSocketMessage {
  action: string;
  [key: string]: unknown;
}

export interface WebSocketCallbacks {
  onPlayersUpdate?: (players: MultiPlayer[]) => void;
  onPlayerJoined?: (playerName: string) => void;
  onNewQuestion?: (question: Question) => void;
  onGameStarted?: () => void;
  onGameUpdated?: (game: Game) => void;
  onAnswerChecked?: (answer: Answer) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
}

export interface WebSocketService {
  connect(game: Game, player: Player, language: string, callbacks: WebSocketCallbacks): WebSocket;
  disconnect(): void;
  send(data: Record<string, unknown>): void;
  isConnected(): boolean;
}

export class WebSocketServiceImpl implements WebSocketService {
  private socket: WebSocket | null = null;
  private callbacks: WebSocketCallbacks = {};
  private retryInterval = 1000;
  private maxRetries = 100;
  private retries = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;

  connect(game: Game, player: Player, language: string, callbacks: WebSocketCallbacks): WebSocket {
    this.callbacks = callbacks;
    this.disconnect(); // Close existing connection

    const socketUrl = this.getSocketUrl(game.token);
    const ws = new WebSocket(socketUrl);

    ws.onopen = () => {
      console.log('WebSocket connection established');
      this.retries = 0; // Reset retry counter on successful connection
      ws.send(JSON.stringify({
        action: 'join_game',
        player_token: player.token,
        language_code: language,
        ...clientInfoPayload(),
      }));
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket Error:', error);
      callbacks.onError?.(error);
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
      callbacks.onClose?.();
      this.socket = null;

      // Attempt reconnection
      if (this.retries < this.maxRetries) {
        this.retries++;
        console.log(`Reconnecting... (${this.retries}/${this.maxRetries})`);
        this.reconnectTimeout = setTimeout(() => {
          if (game && player) {
            this.connect(game, player, language, callbacks);
          }
        }, this.retryInterval);
      } else {
        console.log('Max retries reached. Could not reconnect.');
      }
    };

    this.socket = ws;
    return ws;
  }

  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  send(data: Record<string, unknown>): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    } else {
      console.log('Error sending action. Socket not ready.');
    }
  }

  isConnected(): boolean {
    return this.socket !== null && this.socket.readyState === WebSocket.OPEN;
  }

  private getSocketUrl(gameToken: string): string {
    if (window.location.host === 'localhost:3000') {
      return `ws://127.0.0.1:8050/mpg/${gameToken}`;
    }
    return `wss://birdr.pro/mpg/${gameToken}`;
  }

  private handleMessage(message: WebSocketMessage): void {
    console.log('Message from server:', message.action);

    switch (message.action) {
      case 'update_players':
        this.callbacks.onPlayersUpdate?.(message.players as MultiPlayer[]);
        break;
      case 'player_joined':
        this.callbacks.onPlayerJoined?.(message.player_name as string);
        break;
      case 'new_question':
        this.callbacks.onNewQuestion?.(message.question as Question);
        break;
      case 'game_started':
        this.callbacks.onGameStarted?.();
        break;
      case 'game_updated':
        this.callbacks.onGameUpdated?.(message.game as Game);
        break;
      case 'answer_checked':
        this.callbacks.onAnswerChecked?.(message.answer as Answer);
        break;
      default:
        console.log('Unknown WebSocket action:', message.action);
    }
  }
}

// Default service instance
export const websocketService = new WebSocketServiceImpl();

