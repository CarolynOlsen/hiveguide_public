/**
 * Web-specific storage implementation
 * Uses browser localStorage API
 */

export const storage = {
  async getItem(key: string): Promise<string | null> {
    return localStorage.getItem(key);
  },

  async setItem(key: string, value: string): Promise<void> {
    localStorage.setItem(key, value);
  },

  async removeItem(key: string): Promise<void> {
    localStorage.removeItem(key);
  },

  async clear(): Promise<void> {
    localStorage.clear();
  },
};
