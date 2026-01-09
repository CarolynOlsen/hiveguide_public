import { useState, useCallback, useRef } from 'react';
import { AudioRecordingHook } from './index';
import { apiService } from '../../../mobile/src/services/api';

export const useWebAudioRecording = (config?: any): AudioRecordingHook => {
  const [isRecording, setIsRecording] = useState(false);
  const [transcribedText, setTranscribedText] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        
        try {
          console.log('📤 Sending audio for transcription...');
          const result = await apiService.transcribeAudio(formData);
          console.log('✅ Transcription result:', result);
          
          if (result.status === 'success' && result.transcription) {
            setTranscribedText(result.transcription);
            config?.onTranscriptionUpdate?.(result.transcription);
          } else {
            const errorMsg = 'message' in result ? String(result.message) : 'Unexpected response format';
            setError(errorMsg);
            console.error('❌ Transcription failed:', errorMsg);
          }
        } catch (err: any) {
          const errorMsg = err.message || 'Transcription failed';
          setError(errorMsg);
          console.error('❌ Transcription error:', err);
        }
        
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      recorder.start(1000);
      setIsRecording(true);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  }, [config]);

  const stopRecording = useCallback(async () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  }, [isRecording]);

  return {
    isRecording,
    isStreaming: false,
    transcribedText,
    confidence: 1.0,
    error,
    startRecording,
    stopRecording,
    isStreamingAvailable: false,
  };
};
