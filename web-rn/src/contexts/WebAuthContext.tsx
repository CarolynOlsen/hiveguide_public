import React, { createContext, useContext, ReactNode } from 'react';

interface User {
  id: number;
  email: string;
  is_admin: boolean;
  is_approved: boolean;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  console.log('🟢 WebAuthProvider: Initializing minimal version');
  
  const value: AuthContextType = {
    user: null,
    isAuthenticated: false,
    loading: false,
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