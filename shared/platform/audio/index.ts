// Audio recording hook interface
export interface AudioRecordingHook {
  isRecording: boolean;
  isStreaming: boolean;
  transcribedText: string;
  confidence: number;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  isStreamingAvailable: boolean;
}

// Re-export platform-specific implementations
// Webpack/Metro will automatically select .web.ts or .native.ts
export { useAudioRecording } from './useAudioRecording';
