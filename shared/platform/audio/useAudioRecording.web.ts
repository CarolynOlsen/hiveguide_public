import { useWebAudioRecording } from './web';
import { AudioRecordingHook } from './index';

export const useAudioRecording = (config?: any): AudioRecordingHook => {
  return useWebAudioRecording(config);
};
