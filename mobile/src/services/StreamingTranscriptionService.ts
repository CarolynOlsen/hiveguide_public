/**
 * StreamingTranscriptionService
 * Manages WebSocket connection to Assembly AI for real-time transcription
 */

import { Buffer } from 'buffer';
import { Alert } from 'react-native';
import { httpClient } from './api';

// Note: Don't use API_CONFIG from shared as it defaults to localhost
// Use the same production URL as MobileHttpClient

export interface TranscriptionResult {
  text: string;
  isFinal: boolean;
  confidence: number;
  accumulatedText?: string;
}

export interface StreamingTranscriptionCallbacks {
  onTranscription?: (result: TranscriptionResult) => void;
  onError?: (error: string) => void;
  onReady?: () => void;
  onFinal?: (text: string) => void;
  onFallback?: () => void;
}

export class StreamingTranscriptionService {
  private ws: WebSocket | null = null;
  private callbacks: StreamingTranscriptionCallbacks = {};
  private isConnected = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private audioQueue: ArrayBuffer[] = [];
  private isProcessingQueue = false;
  private accumulatedTranscript: string = '';
  private tokenExpiresAt: number = 0;
  private refreshTimer: any = null;
  private currentToken: string = '';
  private messageCounter: number = 0;

  constructor(callbacks: StreamingTranscriptionCallbacks) {
    this.callbacks = callbacks;
  }

  /**
   * Connect to Assembly AI streaming transcription WebSocket
   */
  async connect(): Promise<void> {
    return new Promise(async (resolve, reject) => {
      try {
        // First, get a temporary token from our backend using the authenticated HTTP client
        console.log('📡 Step 1: Getting Assembly AI token from backend...');
        console.log('Making POST request to /api/assembly-ai-token');

        let tokenResponse;
        try {
          tokenResponse = await httpClient.post<{token: string}>('/api/assembly-ai-token', {});
          console.log('Token response received:', tokenResponse ? 'yes' : 'no');
        } catch (tokenError: any) {
          console.error('❌ Failed to fetch token from backend:', tokenError);
          console.error('Token fetch error details:', {
            message: tokenError?.message,
            status: tokenError?.status,
            statusText: tokenError?.statusText,
            data: tokenError?.data
          });
          reject(new Error('Failed to fetch Assembly AI token from backend: ' + (tokenError?.message || 'Unknown error')));
          return;
        }

        if (!tokenResponse || !tokenResponse.token) {
          console.error('❌ Invalid token response:', tokenResponse);
          reject(new Error('Failed to get transcription token - invalid response from backend'));
          return;
        }

        const { token } = tokenResponse;
        console.log('✅ Got Assembly AI token from backend');
        console.log('Token length:', token?.length);
        console.log('Token first 20 chars:', token?.substring(0, 20) + '...');

        // Track token for refresh (expires in 600 seconds, refresh at 8 minutes)
        this.currentToken = token;
        this.tokenExpiresAt = Date.now() + (600 * 1000); // 10 minutes from now
        this.scheduleTokenRefresh();

        // Connect to Assembly AI v3 WebSocket with the token
        // Use 16kHz sample rate and enable formatted turns for better transcript handling
        const wsUrl = `wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&encoding=pcm_s16le&format_turns=true&token=${token}`;

        console.log('📡 Step 2: Creating WebSocket connection to Assembly AI...');
        console.log('WebSocket URL (without token):', 'wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&encoding=pcm_s16le&format_turns=true&token=...');

        this.ws = new WebSocket(wsUrl);
        console.log('WebSocket object created, waiting for connection...');

        this.ws.onopen = () => {
          console.log('✅ Assembly AI WebSocket CONNECTED!');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.accumulatedTranscript = '';
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.messageCounter += 1;
          console.log('📨 Received message from Assembly AI:', event.data);
          
          // Process message (no alerts, just console logs)
          try {
            const message = JSON.parse(event.data);
            this.handleAssemblyAIMessage(message);
          } catch (error) {
            console.error('Failed to parse Assembly AI message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('❌ Assembly AI WebSocket ERROR:', error);
          console.error('WebSocket URL was:', 'wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&encoding=pcm_s16le&format_turns=true&token=...');
          console.error('Error object:', error);
          console.error('Error type:', typeof error);
          console.error('Error keys:', error ? Object.keys(error) : 'null');

          this.callbacks.onError?.('Transcription connection error');
          reject(new Error('WebSocket connection error'));
        };

        this.ws.onclose = (event) => {
          console.log('❌ Assembly AI WebSocket CLOSED');
          console.log('Close code:', event.code);
          console.log('Close reason:', event.reason);
          this.isConnected = false;

          // If we closed before ever connecting, that's an error
          if (!this.isConnected) {
            reject(new Error(`WebSocket closed before connecting: ${event.code} - ${event.reason || 'No reason provided'}`));
          }
        };

      } catch (error: any) {
        console.error('❌ Exception in connect():', error);
        console.error('Exception details:', {
          message: error?.message,
          name: error?.name,
          stack: error?.stack
        });
        reject(error);
      }
    });
  }

  /**
   * Handle incoming Assembly AI v3 messages
   */
  private handleAssemblyAIMessage(message: any) {
    console.log('Assembly AI v3 message:', message);
    
    // v3 API uses different message structure
    if (message.type === 'receiveSessionBegins' || message.type === 'SessionBegins') {
      console.log('Assembly AI v3 session started');
      this.callbacks.onReady?.();
    } else if (message.type === 'receiveTurn' || message.type === 'Turn' || message.turn_order !== undefined) {
      // v3 uses Turn objects - can be "receiveTurn", "Turn", or just have turn_order field
      const turn = message;
      
      // Extract transcript - it might be in message.transcript OR we need to build it from words
      let transcriptText = turn.transcript || '';
      
      // If transcript is empty but we have words, reconstruct from words array
      if (!transcriptText && turn.words && Array.isArray(turn.words) && turn.words.length > 0) {
        transcriptText = turn.words.map((w: any) => w.text).join(' ');
      }
      
      if (transcriptText && transcriptText.trim()) {
        // Check if this is a final turn or partial
        const isFinal = turn.end_of_turn === true || turn.is_final === true;
        
        // Skip UNformatted FINALS to avoid duplication (Assembly AI sends both formatted and unformatted finals)
        // But always show partials regardless of formatting (we want live feedback)
        if (isFinal && turn.turn_is_formatted === false) {
          console.log('Skipping unformatted final turn:', transcriptText);
          return;
        }
        
        if (isFinal) {
          // Final transcript - add to accumulated text
          if (this.accumulatedTranscript) {
            this.accumulatedTranscript += ' ' + transcriptText;
          } else {
            this.accumulatedTranscript = transcriptText;
          }
          
          console.log('Final transcript:', transcriptText);
          console.log('Accumulated:', this.accumulatedTranscript);
          
          if (this.callbacks.onTranscription) {
            this.callbacks.onTranscription({
              text: transcriptText,
              isFinal: true,
              confidence: turn.confidence || turn.end_of_turn_confidence || 1.0,
              accumulatedText: this.accumulatedTranscript
            });
          }
        } else {
          // Partial transcript - just show preview
          console.log('Partial transcript:', transcriptText);
          
          if (this.callbacks.onTranscription) {
            this.callbacks.onTranscription({
              text: transcriptText,
              isFinal: false,
              confidence: turn.confidence || turn.end_of_turn_confidence || 0.9,
              accumulatedText: undefined  // Partials don't accumulate
            });
          }
        }
      }
    } else if (message.type === 'receiveTermination' || message.type === 'Termination') {
      console.log('Assembly AI v3 session terminated');
      if (this.accumulatedTranscript) {
        this.callbacks.onFinal?.(this.accumulatedTranscript);
      }
    } else if (message.error) {
      console.error('Assembly AI v3 error:', message.error);
      this.callbacks.onError?.(message.error);
    } else {
      console.log('Unknown Assembly AI v3 message type:', message.type || 'unknown');
    }
  }

  /**
   * Send audio chunk to Assembly AI
   * Assembly AI expects raw binary PCM16 data, not base64-encoded JSON
   */
  async sendAudioChunk(audioData: string): Promise<void> {
    if (!this.isConnected || !this.ws) {
      console.warn('WebSocket not connected, discarding audio chunk');
      return;
    }

    try {
      // Convert base64 to binary ArrayBuffer
      // audioData is base64-encoded PCM16 from AudioStreamingModule
      // React Native doesn't have atob, so we use Buffer from 'buffer' package
      const buffer = Buffer.from(audioData, 'base64');
      const bytes = new Uint8Array(buffer);

      // Send as binary frame (Assembly AI expects raw PCM bytes)
      this.ws.send(bytes.buffer);
    } catch (error) {
      console.error('Failed to send audio chunk to Assembly AI:', error);
    }
  }

  /**
   * Process queued audio chunks (not used with Assembly AI - send immediately)
   */
  private async processAudioQueue() {
    // Assembly AI handles buffering internally, so we don't queue
    // This method is kept for compatibility but does nothing
  }

  /**
   * Stop the transcription session
   */
  async stop(): Promise<void> {
    if (!this.ws || !this.isConnected) {
      return;
    }

    try {
      // Send v3 session termination message to Assembly AI
      this.ws.send(JSON.stringify({
        type: 'sendSessionTermination'
      }));
      
      // Wait a bit for the final transcript
      await new Promise<void>(resolve => setTimeout(() => resolve(), 500));
    } catch (error) {
      console.error('Failed to send v3 terminate message:', error);
    }
  }

  /**
   * Disconnect from Assembly AI
   */
  disconnect(): void {
    this.clearTokenRefresh();
    if (this.ws) {
      this.isConnected = false;
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.audioQueue = [];
    this.accumulatedTranscript = '';
    this.currentToken = '';
    this.tokenExpiresAt = 0;
  }

  /**
   * Check if currently connected
   */
  isStreamingConnected(): boolean {
    return this.isConnected;
  }

  /**
   * Schedule token refresh before expiration (refresh at 8 minutes to be safe)
   */
  private scheduleTokenRefresh(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }

    // Refresh token 2 minutes before expiration (8 minutes after creation)
    const refreshIn = Math.max(0, this.tokenExpiresAt - Date.now() - (2 * 60 * 1000));
    
    this.refreshTimer = setTimeout(() => {
      this.refreshToken();
    }, refreshIn);

    console.log(`Token refresh scheduled in ${Math.round(refreshIn / 1000)} seconds`);
  }

  /**
   * Refresh the Assembly AI token and reconnect
   */
  private async refreshToken(): Promise<void> {
    if (!this.isConnected) {
      console.log('Not connected, skipping token refresh');
      return;
    }

    console.log('Refreshing Assembly AI token...');
    
    try {
      // Save current state
      const currentAccumulatedText = this.accumulatedTranscript;
      
      // Get new token using authenticated HTTP client
      const tokenResponse = await httpClient.post<{token: string}>('/api/assembly-ai-token', {});
      
      if (!tokenResponse || !tokenResponse.token) {
        console.error('Failed to refresh Assembly AI token: Invalid response');
        return;
      }
      
      const { token } = tokenResponse;
      
      // Close current connection gracefully
      if (this.ws) {
        this.ws.send(JSON.stringify({
          type: 'sendSessionTermination'
        }));
        this.ws.close();
      }
      
      // Update token info
      this.currentToken = token;
      this.tokenExpiresAt = Date.now() + (600 * 1000);
      this.scheduleTokenRefresh();
      
      // Reconnect with new token
      const wsUrl = `wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&encoding=pcm_s16le&format_turns=true&token=${token}`;
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        console.log('Assembly AI WebSocket reconnected with new token');
        this.isConnected = true;
        // Preserve accumulated transcript across reconnection
        this.accumulatedTranscript = currentAccumulatedText;
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleAssemblyAIMessage(message);
        } catch (error) {
          console.error('Failed to parse Assembly AI message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('Assembly AI WebSocket error after refresh:', error);
        this.callbacks.onError?.('Transcription connection error after refresh');
      };

      this.ws.onclose = (event) => {
        console.log('Assembly AI WebSocket closed after refresh:', event.code, event.reason);
        this.isConnected = false;
      };
      
      console.log('Token refreshed and reconnected successfully');
      
    } catch (error) {
      console.error('Failed to refresh token:', error);
      this.callbacks.onError?.('Failed to refresh session - please restart recording');
    }
  }


  /**
   * Clear token refresh timer
   */
  private clearTokenRefresh(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
}
