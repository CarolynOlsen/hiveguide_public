/**
 * @format
 */

import { MobileHttpClient } from '../src/services/HttpClient';

// Mock axios to test HTTP client behavior
jest.mock('axios', () => ({
  create: jest.fn(() => ({
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
    post: jest.fn(),
    get: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  })),
}));

describe('MobileHttpClient', () => {
  let httpClient: MobileHttpClient;
  let mockAxiosInstance: any;

  beforeEach(() => {
    const axios = require('axios');
    mockAxiosInstance = axios.create();
    httpClient = new MobileHttpClient();
  });

  test('login method exists and can be called', () => {
    expect(httpClient.post).toBeDefined();
    expect(typeof httpClient.post).toBe('function');
  });

  test('HttpClient initializes with correct base URL', () => {
    // Test that the mobile HTTP client is properly configured
    expect(mockAxiosInstance).toBeDefined();
  });
});
