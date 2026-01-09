import React, { useState, useEffect } from 'react';
import { AppRegistry, Text } from 'react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../../mobile/src/contexts/AuthContext';
import BottomTabBar from './components/BottomTabBar';
import WebLayout from './components/WebLayout';

// Import screens
import LoginScreen from '../../mobile/src/screens/LoginScreen';
import HomeScreenWeb from './screens/HomeScreenWeb';
import DashboardScreen from '../../mobile/src/screens/DashboardScreen';
import HivesScreen from '../../mobile/src/screens/HivesScreen';
import InspectionFormScreen from '../../mobile/src/screens/InspectionFormScreen';
import ChatScreen from '../../mobile/src/screens/ChatScreen';

console.log('🚀 React Native Web App initializing...');

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

// Simple router component
function AppRouter() {
  const { isAuthenticated, loading } = useAuth();
  const [currentScreen, setCurrentScreen] = useState('home');

  // Sync with URL
  useEffect(() => {
    const path = window.location.pathname;
    const pathMap: Record<string, string> = {
      '/': 'home',
      '/home': 'home',
      '/login': 'login',
      '/dashboard': 'dashboard',
      '/inspect': 'inspect',
      '/hives': 'hives',
      '/chat': 'chat',
    };
    const screen = pathMap[path] || 'home';
    setCurrentScreen(screen);
  }, []);

  // Handle browser back/forward
  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      if (path === '/' || path === '/home') setCurrentScreen('home');
      else if (path === '/login') setCurrentScreen('login');
      else if (path === '/dashboard') setCurrentScreen('dashboard');
      else if (path === '/inspect') setCurrentScreen('inspect');
      else if (path === '/hives') setCurrentScreen('hives');
      else if (path === '/chat') setCurrentScreen('chat');
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // React to auth changes
  useEffect(() => {
    if (!loading) {
      if (isAuthenticated && currentScreen === 'login') {
        setCurrentScreen('home');
        window.history.pushState(null, '', '/home');
      } else if (!isAuthenticated && currentScreen !== 'login') {
        setCurrentScreen('login');
        window.history.pushState(null, '', '/login');
      }
    }
  }, [isAuthenticated, loading, currentScreen]);

  const navigate = (screenName: string) => {
    setCurrentScreen(screenName);
    const urlMap: Record<string, string> = {
      login: '/login',
      home: '/home',
      dashboard: '/dashboard',
      inspect: '/inspect',
      hives: '/hives',
      chat: '/chat',
    };
    window.history.pushState(null, '', urlMap[screenName] || '/');
  };

  // Mock navigation object for screens that expect it
  const mockNavigation = {
    navigate,
    goBack: () => navigate('home'),
  };

  const renderScreen = () => {
    console.log('🎬 Rendering screen:', currentScreen);
    try {
      switch (currentScreen) {
        case 'login':
          console.log('📱 Rendering LoginScreen');
          return <LoginScreen navigation={mockNavigation} />;
        case 'home':
          return <HomeScreenWeb navigation={mockNavigation} />;
        case 'dashboard':
          return <DashboardScreen />;
        case 'inspect':
          return <InspectionFormScreen />;
        case 'hives':
          return <HivesScreen navigation={mockNavigation} />;
        case 'chat':
          return <ChatScreen />;
        default:
          return <HomeScreenWeb navigation={mockNavigation} />;
      }
    } catch (error) {
      console.error('❌ Screen render error:', error);
      return <Text>Error rendering screen: {String(error)}</Text>;
    }
  };

  if (loading) {
    return null;
  }

  return (
    <WebLayout
      showBottomTabs={isAuthenticated}
      bottomTabs={
        <BottomTabBar currentScreen={currentScreen} onNavigate={navigate} />
      }
    >
      {renderScreen()}
    </WebLayout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </QueryClientProvider>
  );
}

AppRegistry.registerComponent('HiveGuide', () => App);
AppRegistry.runApplication('HiveGuide', {
  rootTag: document.getElementById('root'),
});

console.log('✅ App initialization complete');
