import { ApiService } from '@shared';
import { MobileHttpClient } from './HttpClient';

// Create the HTTP client instance
const httpClient = new MobileHttpClient();

// Create the API service instance using the shared API client
export const apiService = new ApiService(httpClient);

// Export the HTTP client for token management
export { httpClient };

// Export types for convenience
export * from '@shared';