import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { HttpClient, RequestOptions } from '@shared';

export class MobileHttpClient implements HttpClient {
  private client: AxiosInstance;
  private sessionToken: string | null = null;
  
  constructor() {
    // Use hardcoded production URL for now since react-native-config has linking issues
    const baseURL = 'https://hiveguide.up.railway.app';
    
    console.log('📱 MobileHttpClient - Using API URL:', baseURL); // DEBUG
    // Temporarily show URL for debugging
    setTimeout(() => {
      console.warn('DEBUG: API URL being used:', baseURL);
    }, 1000);
    
    this.client = axios.create({
      baseURL,
      timeout: 60000, // 60 seconds for chat/LLM requests
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for debugging and authentication
    this.client.interceptors.request.use(
      (config) => {
        if (__DEV__) {
          console.log(`📡 ${config.method?.toUpperCase()} ${config.url}`);
          console.log(`📡 Full URL: ${config.baseURL}${config.url}`);
        }
        
        // Add session token as Authorization header if available
        if (this.sessionToken && config.headers) {
          config.headers['Authorization'] = `Bearer ${this.sessionToken}`;
        }
        
        return config;
      },
      (error) => {
        console.error('Request error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling with 502 retry logic
    this.client.interceptors.response.use(
      (response) => {
        if (__DEV__) {
          console.log(`✅ ${response.config.method?.toUpperCase()} ${response.config.url} - ${response.status}`);
        }
        return response;
      },
      async (error) => {
        const config = error.config;
        const status = error.response?.status;
        
        if (__DEV__) {
          // Only log non-502 errors prominently, 502s are handled by retry logic
          if (status !== 502) {
            console.error(`❌ ${config?.method?.toUpperCase()} ${config?.url} - ${status || 'Network Error'}`);
          }
        }

        // Retry logic for 502 Bad Gateway errors (Railway cold starts)
        if (status === 502 && config && !config._retryCount) {
          config._retryCount = config._retryCount || 0;
          
          if (config._retryCount < 3) {
            config._retryCount += 1;
            const delay = Math.min(1000 * Math.pow(2, config._retryCount - 1), 5000); // Exponential backoff, max 5s
            
            // Silent retry - no user-visible messages
            if (__DEV__) {
              console.log(`🔄 Retrying 502 error (attempt ${config._retryCount}/3) after ${delay}ms delay...`);
            }
            
            await new Promise<void>(resolve => setTimeout(resolve, delay));
            return this.client(config);
          }
        }
        
        return Promise.reject(error);
      }
    );
  }
  
  // Token management methods
  setSessionToken(token: string) {
    this.sessionToken = token;
  }
  
  clearSessionToken() {
    this.sessionToken = null;
  }
  
  async get<T>(url: string, options?: RequestOptions): Promise<T> {
    const response: AxiosResponse<T> = await this.client.get(url, {
      headers: options?.headers,
      timeout: options?.timeout,
    });
    return response.data;
  }
  
  async post<T>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    const response: AxiosResponse<T> = await this.client.post(url, data, {
      headers: options?.headers,
      timeout: options?.timeout,
    });
    return response.data;
  }
  
  async put<T>(url: string, data?: any, options?: RequestOptions): Promise<T> {
    const response: AxiosResponse<T> = await this.client.put(url, data, {
      headers: options?.headers,
      timeout: options?.timeout,
    });
    return response.data;
  }
  
  async delete<T>(url: string, options?: RequestOptions): Promise<T> {
    const response: AxiosResponse<T> = await this.client.delete(url, {
      headers: options?.headers,
      timeout: options?.timeout,
    });
    return response.data;
  }
  
  async upload<T>(url: string, formData: FormData, options?: RequestOptions): Promise<T> {
    console.log(`🎤 Upload request to: ${url}`);
    const response: AxiosResponse<T> = await this.client.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
        ...options?.headers,
      },
      timeout: options?.timeout || 30000, // Longer timeout for uploads
    });
    console.log(`✅ Upload response status: ${response.status}`, response.data);
    return response.data;
  }
}