// Shared API client utilities for Hive Scribe
// Used by both web and mobile applications

import { 
  ApiResponse, 
  User, 
  Hive, 
  Inspection, 
  InspectionFormData, 
  AuthResponse, 
  LoginResponse,
  ChatMessage, 
  DashboardData,
  Circle,
  CircleMembership,
  CircleCreateRequest,
  InviteMemberRequest,
  PendingUser,
  UserActionRequest
} from './types';

// Base API configuration
export const API_CONFIG = {
  // Default to localhost for development
  // Override in production with environment variables or platform-specific config
  // Use environment detection that works cross-platform
  BASE_URL: (() => {
    // Check if we're in a Node.js environment with proper typing
    if (typeof globalThis !== 'undefined' && 
        typeof (globalThis as any).process !== 'undefined' && 
        (globalThis as any).process.env && 
        (globalThis as any).process.env.API_BASE_URL) {
      return (globalThis as any).process.env.API_BASE_URL;
    }
    // Default for React Native and other environments
    return 'http://localhost:8000';
  })(),
  TIMEOUT: 10000,
};

// HTTP client interface - implement differently for web vs mobile
export interface HttpClient {
  get<T>(url: string, options?: RequestOptions): Promise<T>;
  post<T>(url: string, data?: any, options?: RequestOptions): Promise<T>;
  put<T>(url: string, data?: any, options?: RequestOptions): Promise<T>;
  delete<T>(url: string, options?: RequestOptions): Promise<T>;
  upload<T>(url: string, formData: FormData, options?: RequestOptions): Promise<T>;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
  withCredentials?: boolean;
}

// API endpoints
export const API_ENDPOINTS = {
  // Auth - these match the actual backend routes
  LOGIN: '/login',
  LOGOUT: '/logout',
  REGISTER: '/register',
  ME: '/auth/me',
  
  // Hives
  HIVES: '/hives',
  HIVE_BY_ID: (id: number) => `/hives/${id}`,
  
  // Inspections
  INSPECTIONS: '/inspections',
  INSPECTION_BY_ID: (id: number) => `/inspections/${id}`,
  
  // Admin
  PENDING_USERS: '/admin/pending_users',
  APPROVE_USER: '/admin/approve_user',
  REJECT_USER: '/admin/reject_user',
  
  // Circles
  CIRCLES: '/circles',
  CIRCLE_BY_ID: (id: number) => `/circles/${id}`,
  CIRCLE_INVITE: (id: number) => `/circles/${id}/invite`,
  CIRCLE_MEMBERS: (id: number) => `/circles/${id}/members`,
  CIRCLE_REMOVE_MEMBER: (circleId: number, userId: number) => `/circles/${circleId}/members/${userId}`,
  
  // Chat
  CHAT: '/rag/query',
  
  // Uploads
  UPLOAD: '/upload',
  
  // Transcription
  TRANSCRIBE: '/transcribe',
  ANALYZE: '/analyze_text',
  
  // Dashboard
  DASHBOARD: '/api/dashboard',
};

// Generic API service class
export class ApiService {
  constructor(private httpClient: HttpClient) {}

  // Auth methods
  async login(email: string, password: string): Promise<LoginResponse> {
    return this.httpClient.post<LoginResponse>('/login', { email, password });
  }

  async logout(): Promise<ApiResponse<null>> {
    return this.httpClient.post<ApiResponse<null>>('/logout');
  }

  async register(email: string, password: string): Promise<AuthResponse> {
    return this.httpClient.post<AuthResponse>('/register', { email, password });
  }

  async getCurrentUser(): Promise<ApiResponse<User>> {
    return this.httpClient.get<ApiResponse<User>>('/auth/me');
  }

  // Hive methods
  async getHives(): Promise<Hive[]> {
    return this.httpClient.get<Hive[]>(API_ENDPOINTS.HIVES);
  }

  async getHive(id: number): Promise<Hive> {
    return this.httpClient.get<Hive>(API_ENDPOINTS.HIVE_BY_ID(id));
  }

  async createHive(hive: Omit<Hive, 'id' | 'user_id' | 'created_at' | 'updated_at'>): Promise<Hive> {
    return this.httpClient.post<Hive>(API_ENDPOINTS.HIVES, hive);
  }

  async createHiveWithPhoto(hiveData: {
    nickname: string;
    location?: string;
    description?: string;
    photoUri?: string;
    photoFileName?: string;
    photoType?: string;
  }): Promise<Hive> {
    const formData = new FormData();
    formData.append('nickname', hiveData.nickname);
    if (hiveData.location) {
      formData.append('location', hiveData.location);
    }
    if (hiveData.description) {
      formData.append('description', hiveData.description);
    }
    if (hiveData.photoUri) {
      formData.append('photo', {
        uri: hiveData.photoUri,
        type: hiveData.photoType || 'image/jpeg',
        name: hiveData.photoFileName || 'hive-photo.jpg',
      } as any);
    }
    
    return this.httpClient.upload<Hive>(API_ENDPOINTS.HIVES, formData);
  }

  async updateHive(id: number, hive: Partial<Hive>): Promise<Hive> {
    return this.httpClient.put<Hive>(API_ENDPOINTS.HIVE_BY_ID(id), hive);
  }

  async deleteHive(id: number): Promise<{ status: string; message: string }> {
    return this.httpClient.delete<{ status: string; message: string }>(API_ENDPOINTS.HIVE_BY_ID(id));
  }

  // Inspection methods
  async getInspections(): Promise<Inspection[]> {
    return this.httpClient.get<Inspection[]>(API_ENDPOINTS.INSPECTIONS);
  }

  async getInspection(id: number): Promise<Inspection> {
    return this.httpClient.get<Inspection>(API_ENDPOINTS.INSPECTION_BY_ID(id));
  }

  async getInspectionsByHive(hiveId: number): Promise<Inspection[]> {
    return this.httpClient.get<Inspection[]>(`${API_ENDPOINTS.INSPECTIONS}?hive_id=${hiveId}`);
  }

  async createInspection(hiveId: number, inspection: InspectionFormData): Promise<Inspection> {
    const formData = new FormData();
    formData.append('hive_id', hiveId.toString());
    formData.append('transcription', inspection.transcription || '');
    formData.append('notes', inspection.notes || '');
    formData.append('weather', inspection.weather || '');
    formData.append('temperature', inspection.temperature || '');
    formData.append('queen_visible', inspection.queen_visible?.toString() || 'false');
    formData.append('eggs_visible', inspection.eggs_visible?.toString() || 'false');
    formData.append('larvae_visible', inspection.larvae_visible?.toString() || 'false');
    formData.append('capped_brood_visible', inspection.capped_brood_visible?.toString() || 'false');
    formData.append('laying_pattern', inspection.laying_pattern || '');
    formData.append('activity_level', inspection.activity_level || '');
    
    return this.httpClient.upload<Inspection>(API_ENDPOINTS.INSPECTIONS, formData);
  }

  async createInspectionWithPhotos(hiveId: number, formData: FormData): Promise<Inspection> {
    // FormData is already prepared with all fields including photos
    return this.httpClient.upload<Inspection>(API_ENDPOINTS.INSPECTIONS, formData);
  }

  async updateInspection(id: number, inspection: Partial<InspectionFormData>): Promise<Inspection> {
    return this.httpClient.put<Inspection>(API_ENDPOINTS.INSPECTION_BY_ID(id), inspection);
  }

  async deleteInspection(id: number): Promise<{ status: string; message: string }> {
    return this.httpClient.delete<{ status: string; message: string }>(API_ENDPOINTS.INSPECTION_BY_ID(id));
  }

  // Admin methods
  async getPendingUsers(): Promise<PendingUser[]> {
    return this.httpClient.get<PendingUser[]>(API_ENDPOINTS.PENDING_USERS);
  }

  async approveUser(userId: number): Promise<{ status: string; message: string }> {
    return this.httpClient.post<{ status: string; message: string }>(API_ENDPOINTS.APPROVE_USER, { user_id: userId });
  }

  async rejectUser(userId: number): Promise<{ status: string; message: string }> {
    return this.httpClient.post<{ status: string; message: string }>(API_ENDPOINTS.REJECT_USER, { user_id: userId });
  }

  // Chat methods
  async sendChatMessage(message: string): Promise<{ answer: string; sources?: any[] }> {
    const response = await this.httpClient.post<{ answer: string; sources?: any[]; chunk_count: number; session_id: string }>(
      API_ENDPOINTS.CHAT, 
      { 
        question: message,
        max_chunks: 5,
        session_id: 'chat'
      }
    );
    // Return answer and sources for the UI
    return { answer: response.answer, sources: response.sources };
  }

  // Upload methods
  async uploadFile(file: FormData): Promise<ApiResponse<{ filename: string }>> {
    return this.httpClient.upload<ApiResponse<{ filename: string }>>(API_ENDPOINTS.UPLOAD, file);
  }

  // Transcription methods
  async transcribeAudio(audioFile: FormData): Promise<{ status: string; transcription: string; structured_data?: any }> {
    return this.httpClient.upload<{ status: string; transcription: string; structured_data?: any }>(
      API_ENDPOINTS.TRANSCRIBE,
      audioFile
    );
  }

  // Text analysis method
  async analyzeText(text: string): Promise<{ status: string; transcription: string; structured_data?: any }> {
    return this.httpClient.post<{ status: string; transcription: string; structured_data?: any }>(
      API_ENDPOINTS.ANALYZE,
      { text }
    );
  }

  // Dashboard methods
  async getDashboardData(): Promise<DashboardData> {
    return this.httpClient.get<DashboardData>(API_ENDPOINTS.DASHBOARD);
  }

  // Circle methods
  async getCircles(): Promise<Circle[]> {
    return this.httpClient.get<Circle[]>(API_ENDPOINTS.CIRCLES);
  }

  async createCircle(circle: CircleCreateRequest): Promise<Circle> {
    return this.httpClient.post<Circle>(API_ENDPOINTS.CIRCLES, circle);
  }

  async deleteCircle(id: number): Promise<{ status: string; message: string }> {
    return this.httpClient.delete<{ status: string; message: string }>(API_ENDPOINTS.CIRCLE_BY_ID(id));
  }

  async inviteToCircle(circleId: number, email: string): Promise<{ status: string; message: string }> {
    return this.httpClient.post<{ status: string; message: string }>(API_ENDPOINTS.CIRCLE_INVITE(circleId), { email });
  }

  async getCircleMembers(circleId: number): Promise<CircleMembership[]> {
    return this.httpClient.get<CircleMembership[]>(API_ENDPOINTS.CIRCLE_MEMBERS(circleId));
  }

  async removeCircleMember(circleId: number, userId: number): Promise<{ status: string; message: string }> {
    return this.httpClient.delete<{ status: string; message: string }>(API_ENDPOINTS.CIRCLE_REMOVE_MEMBER(circleId, userId));
  }
}

// Utility functions
export const buildApiUrl = (endpoint: string): string => {
  return `${API_CONFIG.BASE_URL}${endpoint}`;
};

export const isApiError = (response: any): response is { error: string } => {
  return response && typeof response.error === 'string';
};

export const getErrorMessage = (error: any): string => {
  if (isApiError(error)) {
    return error.error;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
};