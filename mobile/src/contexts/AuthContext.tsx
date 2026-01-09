import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
// import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiService, httpClient } from '../services/api';
import { User, LoginResponse } from '@shared';

interface AuthContextType {
  user: User | null;
  profile: User | null;
  isAdmin: boolean;
  isAuthenticated: boolean;
  isApproved: boolean;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signUp: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signOut: () => Promise<{ success: boolean }>;
  checkAuth: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

const USER_STORAGE_KEY = '@HiveGuide:user';

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<User | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sessionToken, setSessionToken] = useState<string | null>(null);

  const loadStoredUser = async () => {
    // TODO: Re-enable AsyncStorage once native module is working
    // For now, just skip loading from storage
    console.log('AsyncStorage disabled - skipping load');
  };

  const saveUserToStorage = async (userData: User) => {
    // TODO: Re-enable AsyncStorage once native module is working
    console.log('AsyncStorage disabled - skipping save');
  };

  const clearStoredUser = async () => {
    // TODO: Re-enable AsyncStorage once native module is working  
    console.log('AsyncStorage disabled - skipping clear');
  };

  // Check authentication status with backend
  const checkAuth = async (): Promise<boolean> => {
    try {
      const response = await apiService.getCurrentUser();
      
      if (response.success && response.data) {
        setUser(response.data);
        setProfile(response.data);
        setIsAdmin(response.data.is_admin || false);
        await saveUserToStorage(response.data);
        return true;
      } else {
        // Not authenticated
        setUser(null);
        setProfile(null);
        setIsAdmin(false);
        await clearStoredUser();
        return false;
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
      setProfile(null);
      setIsAdmin(false);
      await clearStoredUser();
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Initialize auth on app start - just load from storage, don't check with server initially
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        await loadStoredUser();
        setLoading(false); // Set loading to false immediately after loading from storage
      } catch (error) {
        console.error('Auth initialization failed:', error);
        setLoading(false);
      }
    };
    initializeAuth();
  }, []);

  const signIn = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      console.log('🔐 AuthContext: Starting login for:', email);
      const response: LoginResponse = await apiService.login(email, password);
      console.log('🔐 AuthContext: Login response received');
      
      // Backend returns { status: "success", session_token, user } directly
      if (response.status === 'success' && response.session_token && response.user) {
        console.log('🔐 AuthContext: Login successful, extracting data');
        const { session_token, user } = response;
        console.log('🔐 AuthContext: session_token exists:', !!session_token);
        console.log('🔐 AuthContext: user exists:', !!user);
        
        setSessionToken(session_token);
        httpClient.setSessionToken(session_token);
        
        setUser(user);
        setProfile(user);
        setIsAdmin(user.is_admin || false);
        await saveUserToStorage(user);
        
        console.log('🔐 AuthContext: Login complete!');
        return { success: true };
      } else {
        console.log('🔐 AuthContext: Login failed - response.status=', response.status);
        console.log('🔐 AuthContext: Error:', response.message);
        return { success: false, error: response.message || 'Login failed' };
      }
    } catch (error: any) {
      console.error('🔐 AuthContext: Exception during login:', error);
      console.error('🔐 AuthContext: Error message:', error?.message);
      return { 
        success: false, 
        error: error?.message || 'Login failed. Please try again.' 
      };
    }
  };

  const signUp = async (email: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await apiService.register(email, password);
      
      if (response.message) {
        return { success: true };
      } else {
        return { success: false, error: 'Registration failed' };
      }
    } catch (error: any) {
      console.error('Registration failed:', error);
      return { 
        success: false, 
        error: error?.response?.data?.detail || 'Registration failed. Please try again.' 
      };
    }
  };

  const signOut = async (): Promise<{ success: boolean }> => {
    try {
      await apiService.logout();
      setUser(null);
      setProfile(null);
      setIsAdmin(false);
      setSessionToken(null);
      httpClient.clearSessionToken();
      await clearStoredUser();
      return { success: true };
    } catch (error) {
      console.error('Logout failed:', error);
      // Still clear local state even if logout request fails
      setUser(null);
      setProfile(null);
      setIsAdmin(false);
      setSessionToken(null);
      httpClient.clearSessionToken();
      await clearStoredUser();
      return { success: false };
    }
  };

  const value: AuthContextType = {
    user,
    profile,
    isAdmin,
    loading,
    signIn,
    signUp,
    signOut,
    isAuthenticated: !!user,
    isApproved: profile?.is_approved || false,
    checkAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};