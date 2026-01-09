// Mock for react-native-safe-area-context on web
import React from 'react';

export const SafeAreaProvider = ({ children }) => children;

export const SafeAreaView = ({ children, style, ...props }) => 
  React.createElement('div', { style, ...props }, children);

export const useSafeAreaInsets = () => ({
  top: 0,
  bottom: 0,
  left: 0,
  right: 0,
});

export const useSafeAreaFrame = () => ({
  x: 0,
  y: 0,
  width: window.innerWidth || 0,
  height: window.innerHeight || 0,
});

export const SafeAreaListener = null;

// Additional exports needed by React Navigation
export const SafeAreaInsetsContext = React.createContext({
  top: 0,
  bottom: 0,
  left: 0,
  right: 0,
});

export const initialWindowMetrics = {
  insets: { top: 0, bottom: 0, left: 0, right: 0 },
  frame: { x: 0, y: 0, width: 0, height: 0 },
};

export default {
  SafeAreaProvider,
  SafeAreaView,
  useSafeAreaInsets,
  useSafeAreaFrame,
  SafeAreaListener,
  SafeAreaInsetsContext,
  initialWindowMetrics,
};