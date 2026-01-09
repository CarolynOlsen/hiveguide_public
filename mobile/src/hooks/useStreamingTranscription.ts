/**
 * useStreamingTranscription Hook
 * Manages real-time audio streaming and transcription
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { Platform, Alert } from 'react-native';
import { AudioStreamingModule, AudioChunk } from '../services/AudioStreamingModule';
import { StreamingTranscriptionService, TranscriptionResult } from '../services/StreamingTranscriptionService';
// Note: Don't use API_CONFIG from shared as it defaults to localhost
// Use the same production URL as MobileHttpClient

export interface UseStreamingTranscriptionResult {
  isStreaming: boolean;
  isConnecting: boolean;
  transcribedText: string;
  confidence: number;
  error: string | null;
  startStreaming: () => Promise<void>;
  stopStreaming: () => Promise<void>;
  isStreamingAvailable: boolean;
}

export interface StreamingTranscriptionConfig {
  sampleRate?: number; // Default: 16000
  chunkDuration?: number; // Default: 300ms
  onTranscriptionUpdate?: (text: string) => void;
  onFallbackNeeded?: () => void;
}

/**
 * Hook for managing real-time audio streaming and transcription
 */
export function useStreamingTranscription(
  config: StreamingTranscriptionConfig = {}
): UseStreamingTranscriptionResult {
  const {
    sampleRate = 16000,
    chunkDuration = 300,
    onTranscriptionUpdate,
    onFallbackNeeded
  } = config;

  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [transcribedText, setTranscribedText] = useState('');
  const [confidence, setConfidence] = useState(1.0);
  const [error, setError] = useState<string | null>(null);
  const [isStreamingAvailable, setIsStreamingAvailable] = useState(true);

  const transcriptionServiceRef = useRef<StreamingTranscriptionService | null>(null);
  const audioSubscriptionsRef = useRef<any[]>([]);
  const accumulatedTextRef = useRef('');
  const chunkCounterRef = useRef(0);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (transcriptionServiceRef.current) {
        transcriptionServiceRef.current.disconnect();
      }
      audioSubscriptionsRef.current.forEach(sub => sub.remove());
      AudioStreamingModule.removeAllListeners();
    };
  }, []);

  const handleTranscription = useCallback((result: TranscriptionResult) => {
    console.log('Transcription result:', result);
    
    if (result.accumulatedText) {
      // Final transcript - use Assembly AI's accumulated text (includes everything so far)
      accumulatedTextRef.current = result.accumulatedText;
      setTranscribedText(result.accumulatedText);
      onTranscriptionUpdate?.(result.accumulatedText);
      setConfidence(result.confidence);
    } else if (result.text && !result.isFinal) {
      // Partial transcript - show it live by adding to finals (but don't save to ref)
      // This gives live feedback without duplicating when final arrives
      const liveText = accumulatedTextRef.current + (accumulatedTextRef.current ? ' ' : '') + result.text;
      setTranscribedText(liveText);
      onTranscriptionUpdate?.(liveText);
      setConfidence(result.confidence);
    }
  }, [onTranscriptionUpdate]);

  const handleError = useCallback((errorMsg: string) => {
    console.error('Streaming transcription error:', errorMsg);
    setError(errorMsg);
    // Don't show alert - just log the error
  }, []);

  const handleFallback = useCallback(() => {
    console.log('Falling back to batch transcription');
    setIsStreamingAvailable(false);
    onFallbackNeeded?.();
    // Don't show alert - streaming will just be unavailable
  }, [onFallbackNeeded]);

  const startStreaming = useCallback(async () => {
    console.log('=== startStreaming called ===');

    if (isStreaming) {
      console.log('Already streaming - aborting');
      return;
    }

    // Check platform
    if (Platform.OS !== 'ios') {
      setIsStreamingAvailable(false);
      console.log('Streaming transcription only available on iOS');
      throw new Error('Streaming only available on iOS');
    }

    // Check if running in simulator
    if (__DEV__ && Platform.OS === 'ios') {
      console.log('Development mode: iOS device detected');
    }

    // Check if AudioStreamingModule is available
    console.log('Checking AudioStreamingModule availability...');
    try {
      // Test if the module is available by checking if it has the required methods
      if (!AudioStreamingModule || typeof AudioStreamingModule.startStreaming !== 'function') {
        console.error('AudioStreamingModule not available or not properly linked');
        setIsStreamingAvailable(false);
        onFallbackNeeded?.();
        throw new Error('Audio streaming module not available');
      }
      console.log('✅ AudioStreamingModule is available');
    } catch (moduleError) {
      console.error('AudioStreamingModule check failed:', moduleError);
      setIsStreamingAvailable(false);
      onFallbackNeeded?.();
      throw new Error('Audio streaming module check failed: ' + moduleError);
    }

    // Use production URL for streaming
    const baseUrl = 'https://hiveguide.up.railway.app';

    try {
      console.log('Setting up streaming service...');
      setIsConnecting(true);
      setError(null);
      accumulatedTextRef.current = '';
      setTranscribedText('');

      // Create transcription service
      const service = new StreamingTranscriptionService({
        onTranscription: handleTranscription,
        onError: handleError,
        onReady: () => {
          console.log('✅ Transcription service ready, starting audio capture');
        },
        onFinal: (text) => {
          console.log('Final transcription received:', text);
          accumulatedTextRef.current = text;
          setTranscribedText(text);
          onTranscriptionUpdate?.(text);
        },
        onFallback: handleFallback
      });

      transcriptionServiceRef.current = service;

      // Try to connect to transcription service with timeout
      console.log('Step 1: Connecting to Assembly AI WebSocket...');
      const connectTimeout = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('WebSocket connection timeout after 5 seconds')), 5000)
      );

      try {
        await Promise.race([service.connect(), connectTimeout]);
        console.log('✅ WebSocket connected successfully');
      } catch (connectError: any) {
        console.error('❌ Failed to connect to Assembly AI WebSocket:', connectError);
        console.error('Error details:', {
          message: connectError?.message,
          name: connectError?.name,
          stack: connectError?.stack
        });

        // Clean up
        setIsConnecting(false);
        setIsStreaming(false);
        setIsStreamingAvailable(false);

        if (transcriptionServiceRef.current) {
          transcriptionServiceRef.current.disconnect();
          transcriptionServiceRef.current = null;
        }

        // Throw error so caller knows it failed
        throw new Error('WebSocket connection failed: ' + (connectError?.message || 'Unknown error'));
      }

      // Set up diagnostic listener (console only, no alerts)
      const diagnosticSubscription = AudioStreamingModule.onDiagnostic((event) => {
        console.log('🔍 DIAGNOSTIC:', event);
      });
      audioSubscriptionsRef.current.push(diagnosticSubscription);

      // Set up audio chunk listener
      chunkCounterRef.current = 0;
      const audioSubscription = AudioStreamingModule.onAudioChunk((chunk: AudioChunk) => {
        chunkCounterRef.current += 1;
        
        // Send audio chunk to transcription service
        service.sendAudioChunk(chunk.data).catch(err => {
          console.error('Failed to send audio chunk:', err);
        });
      });

      audioSubscriptionsRef.current.push(audioSubscription);

      // Start audio streaming with error handling
      console.log('Starting audio streaming...');
      console.log('🔴🔴🔴 ABOUT TO CALL AudioStreamingModule.startStreaming() 🔴🔴🔴');
      console.log('AudioStreamingModule object:', AudioStreamingModule);
      console.log('startStreaming method type:', typeof AudioStreamingModule.startStreaming);
      console.log('Parameters: sampleRate =', sampleRate, ', chunkDuration =', chunkDuration);
      try {
        console.log('🔴 Calling startStreaming NOW...');
        // Call the wrapper with config object (wrapper handles calling native with two params)
        await AudioStreamingModule.startStreaming({ sampleRate, chunkDuration });
        console.log('✅✅✅ AudioStreamingModule.startStreaming() returned successfully!');
      } catch (audioError: any) {
        console.error('🛑🛑🛑 AudioStreamingModule.startStreaming FAILED:', audioError);
        
        // Check if it's a simulator limitation
        if (audioError.message && audioError.message.includes('SIMULATOR_LIMITATION')) {
          console.log('Audio streaming not supported in iOS Simulator');
          setIsStreamingAvailable(false);
          onFallbackNeeded?.();
          return;
        }
        
        throw new Error(`Audio streaming failed: ${audioError.message || audioError}`);
      }

      setIsStreaming(true);
      setIsConnecting(false);
      console.log('Streaming started successfully');

    } catch (error: any) {
      console.error('Failed to start streaming:', error);
      setError(error.message || 'Failed to start streaming');
      setIsConnecting(false);
      setIsStreaming(false);

      // Don't show alert - just log and disable streaming
      console.log('Streaming unavailable - feature disabled');

      // Clean up
      if (transcriptionServiceRef.current) {
        transcriptionServiceRef.current.disconnect();
        transcriptionServiceRef.current = null;
      }
      
      onFallbackNeeded?.();
      
      // Re-throw so the caller knows it failed
      throw error;
    }
  }, [
    isStreaming,
    sampleRate,
    chunkDuration,
    handleTranscription,
    handleError,
    handleFallback,
    onTranscriptionUpdate,
    onFallbackNeeded
  ]);

  const stopStreaming = useCallback(async () => {
    console.log('🛑🛑🛑 stopStreaming() CALLED 🛑🛑🛑');
    console.log('Current isStreaming state:', isStreaming);
    console.log('Stack trace:', new Error().stack);

    if (!isStreaming) {
      console.log('Not currently streaming - aborting stop');
      return;
    }

    try {
      console.log('Proceeding to stop streaming...');

      // Stop transcription service
      if (transcriptionServiceRef.current) {
        await transcriptionServiceRef.current.stop();
      }

      // Stop audio streaming
      await AudioStreamingModule.stopStreaming();

      // Clean up
      audioSubscriptionsRef.current.forEach(sub => sub.remove());
      audioSubscriptionsRef.current = [];

      if (transcriptionServiceRef.current) {
        transcriptionServiceRef.current.disconnect();
        transcriptionServiceRef.current = null;
      }

      setIsStreaming(false);
      console.log('Streaming stopped successfully');

    } catch (error: any) {
      console.error('Failed to stop streaming:', error);
      setError(error.message || 'Failed to stop streaming');
      // Don't show alert - just log the error
    }
  }, [isStreaming]);

  return {
    isStreaming,
    isConnecting,
    transcribedText,
    confidence,
    error,
    startStreaming,
    stopStreaming,
    isStreamingAvailable
  };
}
