// Shared TypeScript types for Hive Scribe
// Used by both web and mobile applications

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
  is_approved: boolean;
  created_at: string;
}

export interface Hive {
  id: number;
  user_id: number;
  nickname: string;  // Changed from 'name' to match web app
  location?: string;
  description?: string;
  photo_url?: string;
  created_at: string;
  updated_at: string;
}

export interface Inspection {
  id: number;
  hive_id: number;
  user_id: number;
  inspection_date: string;
  weather: string;
  temperature: string;
  brood_pattern: string;
  queen_seen: boolean;
  queen_cells: boolean;
  swarm_cells: boolean;
  honey_stores: string;
  pollen_stores: string;
  population: string;
  temperament: string;
  diseases_pests: string;
  treatments_applied: string;
  notes: string;
  photo_url?: string;
  transcription?: string;
  analysis?: string;
  created_at: string;
  updated_at: string;
  // Additional optional fields (used by mobile app)
  queen_visible?: boolean;
  eggs_visible?: boolean;
  larvae_visible?: boolean;
  capped_brood_visible?: boolean;
  laying_pattern?: string;
  activity_level?: string;
}

export interface InspectionFormData {
  weather: string;
  temperature: string;
  brood_pattern: string;
  queen_seen: boolean;
  queen_cells: boolean;
  swarm_cells: boolean;
  honey_stores: string;
  pollen_stores: string;
  population: string;
  temperament: string;
  diseases_pests: string;
  treatments_applied: string;
  notes: string;
  photo?: File | string;
  // Additional optional fields (used by mobile app)
  transcription?: string;
  queen_visible?: boolean;
  eggs_visible?: boolean;
  larvae_visible?: boolean;
  capped_brood_visible?: boolean;
  laying_pattern?: string;
  activity_level?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

export interface AuthResponse {
  message: string;
  user?: User;
}

export interface LoginResponse {
  status: string;
  message: string;
  session_token: string;
  user: User;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface WeatherOption {
  value: string;
  label: string;
}

export interface TemperatureOption {
  value: string;
  label: string;
}

// Dashboard-specific types
export interface DashboardData {
  apiaries: { [location: string]: HiveWithStatus[] };
  summary: {
    urgent: number;
    attention: number;
    good: number;
  };
  total_hives: number;
  urgent_count: number;
  attention_count: number;
  good_count: number;
}

export interface HiveWithStatus extends Hive {
  urgency_color: 'green' | 'yellow' | 'red';
  days_since_inspection: number | null;
  last_inspection_date: string | null;
  action_items: ActionItem[];
}

export interface ActionItem {
  description: string;
  priority: 'urgent' | 'high' | 'medium' | 'low';
  timeframe_days?: number;
}

// Circle/Sharing types
export interface Circle {
  id: number;
  name: string;
  description?: string;
  owner_id: number;
  created_at: string;
}

export interface CircleMembership {
  id: number;
  circle_id: number;
  user_id: number;
  added_at: string;
  user_email: string;
}

export interface CircleCreateRequest {
  name: string;
  description?: string;
}

export interface InviteMemberRequest {
  email: string;
}

// Admin types
export interface PendingUser {
  id: number;
  email: string;
  created_at: string;
}

export interface UserActionRequest {
  user_id: number;
}

// Streaming Transcription Types
export interface AudioChunk {
  data: string; // Base64 encoded audio data
  timestamp: number;
  chunkIndex: number;
}

export interface TranscriptionResult {
  text: string;
  isFinal: boolean;
  confidence: number;
  wordTimestamps?: WordTimestamp[];
}

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
  confidence: number;
}

export interface StreamingTranscriptionConfig {
  sampleRate: number;
  chunkDuration: number; // milliseconds
  audioFormat: string;
  language?: string;
}

export interface StreamingState {
  status: 'idle' | 'connecting' | 'streaming' | 'stopping' | 'error';
  error?: string;
  transcribedText: string;
  confidence: number;
}

// WebSocket message types for streaming transcription
export interface WSTranscriptionMessage {
  type: 'audio' | 'start' | 'stop' | 'error';
  payload?: any;
}

export interface WSTranscriptionResponse {
  type: 'transcription' | 'error' | 'final';
  text?: string;
  isFinal?: boolean;
  confidence?: number;
  wordTimestamps?: WordTimestamp[];
  error?: string;
}