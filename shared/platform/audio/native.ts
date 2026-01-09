import { AudioRecordingHook } from './index';

export const useNativeAudioRecording = (config?: any): AudioRecordingHook => {
  // Lazy load to avoid bundling mobile-specific code in web build
  const { useStreamingTranscription } = require('../../../mobile/src/hooks/useStreamingTranscription');
  const streamingHook = useStreamingTranscription(config);
  
  return {
    isRecording: streamingHook.isStreaming,
    isStreaming: streamingHook.isStreaming,
    transcribedText: streamingHook.transcribedText,
    confidence: streamingHook.confidence,
    error: streamingHook.error,
    startRecording: streamingHook.startStreaming,
    stopRecording: streamingHook.stopStreaming,
    isStreamingAvailable: streamingHook.isStreamingAvailable,
  };
};
