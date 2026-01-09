/**
 * Platform-agnostic storage type definitions
 * 
 * This is a .d.ts file (TypeScript declarations ONLY - no runtime code)
 * Webpack will resolve to storage.web.ts or storage.native.ts at build time
 */

export interface Storage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
  clear(): Promise<void>;
}

export const storage: Storage;
