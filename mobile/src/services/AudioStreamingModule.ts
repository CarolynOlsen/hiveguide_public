/**
 * AudioStreamingModule - Native iOS audio streaming wrapper
 * Provides real-time audio capture using AVAudioEngine
 */

import { NativeModules, NativeEventEmitter, Platform } from 'react-native';

interface AudioStreamingModuleInterface {
  startStreaming(sampleRate: number, chunkDuration: number): Promise<boolean>;
  stopStreaming(): Promise<boolean>;
  isCurrentlyStreaming(): Promise<boolean>;
  requestMicrophonePermission(): Promise<boolean>;
}

const LINKING_ERROR =
  `The package 'AudioStreamingModule' doesn't seem to be linked. Make sure: \n\n` +
  Platform.select({ ios: "- You have run 'pod install'\n", default: '' }) +
  '- You rebuilt the app after installing the package\n' +
  '- You are running on a physical device or iOS Simulator\n';

const AudioStreamingModuleNative = NativeModules.AudioStreamingModule
  ? NativeModules.AudioStreamingModule
  : new Proxy(
      {},
      {
        get() {
          throw new Error(LINKING_ERROR);
        },
      }
    ) as AudioStreamingModuleInterface;

// Create event emitter
const eventEmitter = new NativeEventEmitter(AudioStreamingModuleNative);

export interface AudioChunk {
  data: string; // Base64 encoded audio data
  timestamp: number;
  chunkIndex: number;
}

export interface DiagnosticEvent {
  step: string;
  message: string;
  chunkIndex?: number;
}

export interface AudioStreamingConfig {
  sampleRate: number; // 16000 recommended for Deepgram
  chunkDuration: number; // milliseconds, 200-400 recommended
}

export class AudioStreamingModule {
  private static listeners: Map<string, any> = new Map();

  /**
   * Start streaming audio
   * @param config Audio streaming configuration
   * @returns Promise that resolves when streaming starts
   */
  static async startStreaming(config: AudioStreamingConfig): Promise<void> {
    const { sampleRate, chunkDuration } = config;
    await AudioStreamingModuleNative.startStreaming(sampleRate, chunkDuration);
  }

  /**
   * Stop streaming audio
   * @returns Promise that resolves when streaming stops
   */
  static async stopStreaming(): Promise<void> {
    await AudioStreamingModuleNative.stopStreaming();
  }

  /**
   * Check if currently streaming
   * @returns Promise that resolves to streaming status
   */
  static async isStreaming(): Promise<boolean> {
    return await AudioStreamingModuleNative.isCurrentlyStreaming();
  }

  /**
   * Request microphone permission (iOS only)
   * @returns Promise that resolves to true if permission granted, rejects if denied
   */
  static async requestMicrophonePermission(): Promise<boolean> {
    return await AudioStreamingModuleNative.requestMicrophonePermission();
  }

  /**
   * Subscribe to audio chunks
   * @param callback Function to call when audio chunk is received
   * @returns Subscription object with remove() method
   */
  static onAudioChunk(callback: (chunk: AudioChunk) => void) {
    const subscription = eventEmitter.addListener('onAudioChunk', callback);
    this.listeners.set('onAudioChunk', subscription);
    return subscription;
  }

  /**
   * Subscribe to streaming errors
   * @param callback Function to call when error occurs
   * @returns Subscription object with remove() method
   */
  static onError(callback: (error: { message: string }) => void) {
    const subscription = eventEmitter.addListener('onStreamingError', callback);
    this.listeners.set('onStreamingError', subscription);
    return subscription;
  }

  /**
   * Subscribe to streaming started event
   * @param callback Function to call when streaming starts
   * @returns Subscription object with remove() method
   */
  static onStreamingStarted(callback: () => void) {
    const subscription = eventEmitter.addListener('onStreamingStarted', callback);
    this.listeners.set('onStreamingStarted', subscription);
    return subscription;
  }

  /**
   * Subscribe to streaming stopped event
   * @param callback Function to call when streaming stops
   * @returns Subscription object with remove() method
   */
  static onStreamingStopped(callback: () => void) {
    const subscription = eventEmitter.addListener('onStreamingStopped', callback);
    this.listeners.set('onStreamingStopped', subscription);
    return subscription;
  }

  /**
   * Subscribe to diagnostic events for debugging
   * @param callback Function to call when diagnostic event occurs
   * @returns Subscription object with remove() method
   */
  static onDiagnostic(callback: (event: DiagnosticEvent) => void) {
    const subscription = eventEmitter.addListener('onDiagnostic', callback);
    this.listeners.set('onDiagnostic', subscription);
    return subscription;
  }

  /**
   * Remove all event listeners
   */
  static removeAllListeners() {
    this.listeners.forEach((subscription) => subscription.remove());
    this.listeners.clear();
  }
}

export default AudioStreamingModule;
