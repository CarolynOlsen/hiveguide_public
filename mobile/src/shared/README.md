# Shared Code for Hive Scribe

This directory contains TypeScript code shared between the web and mobile applications.

## Files

### `types.ts`
- Common TypeScript interfaces and types
- API response formats
- Data models (User, Hive, Inspection, etc.)

### `api-client.ts`
- Shared API service layer
- HTTP client interface for platform-specific implementations
- Standardized API endpoints and methods

## Usage

### Web Application
```typescript
// web/src/lib/api.js
import { ApiService, API_CONFIG } from '../../shared/api-client';
import { HttpClient } from '../../shared/api-client';

// Implement HttpClient using fetch or axios
class WebHttpClient implements HttpClient {
  // Implementation using fetch/axios
}

const apiService = new ApiService(new WebHttpClient());
```

### Mobile Application
```typescript
// mobile/src/services/api.ts
import { ApiService, API_CONFIG } from '../../shared/api-client';
import { HttpClient } from '../../shared/api-client';

// Implement HttpClient using React Native's fetch or axios
class MobileHttpClient implements HttpClient {
  // Implementation for React Native
}

const apiService = new ApiService(new MobileHttpClient());
```

## Benefits

1. **Type Safety**: Shared types ensure consistency between web and mobile
2. **DRY Principle**: No duplicate API logic across platforms
3. **Easier Maintenance**: Update API contracts in one place
4. **Consistency**: Same data structures and validation across platforms