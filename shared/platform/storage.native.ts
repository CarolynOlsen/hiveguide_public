/**
 * Native-specific storage implementation
 * Uses @react-native-async-storage/async-storage
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

export const storage = {
  async getItem(key: string): Promise<string | null> {
    return AsyncStorage.getItem(key);
  },

  async setItem(key: string, value: string): Promise<void> {
    return AsyncStorage.setItem(key, value);
  },

  async removeItem(key: string): Promise<void> {
    return AsyncStorage.removeItem(key);
  },

  async clear(): Promise<void> {
    return AsyncStorage.clear();
  },
};
