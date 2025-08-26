/**
 * WebSocket hook for connecting to Python simulation
 * Handles connection lifecycle, message parsing, and error states
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { IncomingMessage, OutgoingMessage } from '../types/game';

export interface WebSocketConfig {
  readonly url: string;
  readonly reconnectAttempts?: number;
  readonly reconnectDelay?: number;
}

export interface WebSocketState {
  readonly isConnected: boolean;
  readonly isConnecting: boolean;
  readonly error: string | null;
  readonly lastMessage: IncomingMessage | null;
}

interface UseWebSocketReturn extends WebSocketState {
  readonly sendMessage: (message: OutgoingMessage) => void;
  readonly connect: () => void;
  readonly disconnect: () => void;
}

const DEFAULT_CONFIG: Required<WebSocketConfig> = {
  url: 'ws://localhost:8765',
  reconnectAttempts: 5,
  reconnectDelay: 1000
};

export function useWebSocket(config: WebSocketConfig = DEFAULT_CONFIG): UseWebSocketReturn {
  const fullConfig = { ...DEFAULT_CONFIG, ...config };
  
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isConnecting: false,
    error: null,
    lastMessage: null
  });

  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const updateState = useCallback((updates: Partial<WebSocketState>) => {
    setState(prevState => ({ ...prevState, ...updates }));
  }, []);

  const parseMessage = useCallback((data: string): IncomingMessage | null => {
    try {
      const parsed = JSON.parse(data) as unknown;
      
      if (typeof parsed !== 'object' || parsed === null) {
        console.error('WebSocket: Invalid message format - not an object');
        return null;
      }
      
      const message = parsed as Record<string, unknown>;
      
      if (typeof message.type !== 'string') {
        console.error('WebSocket: Invalid message format - missing type field');
        return null;
      }

      // Type narrowing based on message type
      switch (message.type) {
        case 'game_state':
        case 'level':
        case 'error':
          return message as IncomingMessage;
        default:
          console.warn(`WebSocket: Unknown message type: ${message.type}`);
          return null;
      }
    } catch (error) {
      console.error('WebSocket: Failed to parse message:', error);
      return null;
    }
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    const message = parseMessage(event.data);
    if (message !== null) {
      updateState({ lastMessage: message, error: null });
    }
  }, [parseMessage, updateState]);

  const handleError = useCallback((event: Event) => {
    console.error('WebSocket error:', event);
    updateState({ 
      error: 'WebSocket connection error',
      isConnected: false,
      isConnecting: false
    });
  }, [updateState]);

  const handleClose = useCallback(() => {
    updateState({ 
      isConnected: false,
      isConnecting: false
    });

    // Attempt to reconnect if we haven't exceeded the limit
    if (reconnectAttemptsRef.current < fullConfig.reconnectAttempts) {
      reconnectAttemptsRef.current += 1;
      
      updateState({
        error: `Connection lost. Reconnecting... (${reconnectAttemptsRef.current}/${fullConfig.reconnectAttempts})`
      });

      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, fullConfig.reconnectDelay * reconnectAttemptsRef.current);
    } else {
      updateState({
        error: 'Connection failed. Max reconnection attempts exceeded.'
      });
    }
  }, [fullConfig.reconnectAttempts, fullConfig.reconnectDelay, updateState]);

  const handleOpen = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    updateState({
      isConnected: true,
      isConnecting: false,
      error: null
    });
  }, [updateState]);

  const connect = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.CONNECTING ||
        websocketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    clearReconnectTimeout();
    
    updateState({ 
      isConnecting: true,
      error: null
    });

    try {
      websocketRef.current = new WebSocket(fullConfig.url);
      
      websocketRef.current.addEventListener('open', handleOpen);
      websocketRef.current.addEventListener('message', handleMessage);
      websocketRef.current.addEventListener('error', handleError);
      websocketRef.current.addEventListener('close', handleClose);
      
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      updateState({
        error: 'Failed to create WebSocket connection',
        isConnecting: false
      });
    }
  }, [fullConfig.url, handleOpen, handleMessage, handleError, handleClose, clearReconnectTimeout, updateState]);

  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    reconnectAttemptsRef.current = fullConfig.reconnectAttempts; // Prevent reconnection
    
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }
    
    updateState({
      isConnected: false,
      isConnecting: false,
      error: null
    });
  }, [fullConfig.reconnectAttempts, clearReconnectTimeout, updateState]);

  const sendMessage = useCallback((message: OutgoingMessage) => {
    if (!websocketRef.current || websocketRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket: Cannot send message - not connected');
      updateState({ error: 'Cannot send message - not connected' });
      return;
    }

    try {
      const serialized = JSON.stringify(message);
      websocketRef.current.send(serialized);
    } catch (error) {
      console.error('WebSocket: Failed to send message:', error);
      updateState({ error: 'Failed to send message' });
    }
  }, [updateState]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearReconnectTimeout();
      if (websocketRef.current) {
        websocketRef.current.close();
      }
    };
  }, [clearReconnectTimeout]);

  return {
    ...state,
    sendMessage,
    connect,
    disconnect
  };
}