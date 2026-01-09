import { useNativeAudioRecording } from './native';
import { AudioRecordingHook } from './index';

export const useAudioRecording = (config?: any): AudioRecordingHook => {
  return useNativeAudioRecording(config);
};
