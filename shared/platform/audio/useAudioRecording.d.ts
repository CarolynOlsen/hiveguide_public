/**
 * Platform-agnostic audio recording type definitions
 * 
 * This is a .d.ts file (TypeScript declarations ONLY - no runtime code)
 * Webpack will resolve to useAudioRecording.web.ts or useAudioRecording.native.ts at build time
 */

import { AudioRecordingHook } from './index';

export function useAudioRecording(config?: any): AudioRecordingHook;
