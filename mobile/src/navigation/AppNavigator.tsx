import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createStackNavigator } from '@react-navigation/stack';
import { Text, View, ActivityIndicator, StyleSheet } from 'react-native';

// Screen imports
import LoginScreen from '../screens/LoginScreen';
import HomeScreen from '../screens/HomeScreen';
import HivesScreen from '../screens/HivesScreen';
import InspectionFormScreen from '../screens/InspectionFormScreen';
import ChatScreen from '../screens/ChatScreen';
import DashboardScreen from '../screens/DashboardScreen';
import AddHiveScreen from '../screens/AddHiveScreen';
import EditHiveScreen from '../screens/EditHiveScreen';
import MoreScreen from '../screens/MoreScreen';
import ViewInspectionsScreen from '../screens/ViewInspectionsScreen';
import HiveSharingScreen from '../screens/HiveSharingScreen';
import AdminScreen from '../screens/AdminScreen';

// Context
import { useAuth } from '../contexts/AuthContext';

const Tab = createBottomTabNavigator();
const RootStack = createStackNavigator();
const HomeStack = createStackNavigator();
const InspectStack = createStackNavigator();
const ChatStack = createStackNavigator();
const MoreStack = createStackNavigator();

// Shared header style configuration
const headerStyle = {
  backgroundColor: '#fbeee6',
  borderBottomWidth: 0,
  shadowColor: 'transparent',
};

const headerTitleStyle = {
  fontWeight: 'bold' as const,
  fontSize: 22,
  color: '#a67c52',
};

// Common screen options to hide back button
const commonScreenOptions = {
  headerStyle,
  headerTitleStyle,
  headerLeft: () => null, // Hide back button
};

// Simple tab bar icon component
const TabBarIcon = ({ name, focused }: { name: string; focused: boolean }) => (
  <Text style={{ fontSize: 12, color: focused ? '#a67c52' : '#6d4c1b' }}>
    {name}
  </Text>
);

// Helper to create stack screens with shared config
const createStackScreen = (Stack: any, name: string, component: any, title: string) => (
  <Stack.Screen 
    key={name}
    name={name} 
    component={component}
    options={{ title, ...commonScreenOptions }}
  />
);

// Stack navigator for Home tab
function HomeStackNavigator() {
  return (
    // @ts-ignore - React Navigation 7 Navigator id typing issue
    <HomeStack.Navigator screenOptions={{ headerStyle, headerTitleStyle }}>
      {createStackScreen(HomeStack, 'HomeScreen', HomeScreen, 'Home')}
      {createStackScreen(HomeStack, 'Dashboard', DashboardScreen, 'Dashboard')}
      {createStackScreen(HomeStack, 'Hives', HivesScreen, 'My Hives')}
      {createStackScreen(HomeStack, 'AddHive', AddHiveScreen, 'Add New Hive')}
      {createStackScreen(HomeStack, 'EditHive', EditHiveScreen, 'Edit Hive')}
    </HomeStack.Navigator>
  );
}

// Stack navigator for Inspect tab (just InspectionForm)
function InspectStackNavigator() {
  return (
    // @ts-ignore - React Navigation 7 Navigator id typing issue
    <InspectStack.Navigator 
      screenOptions={{ headerStyle, headerTitleStyle }}
    >
      {createStackScreen(InspectStack, 'InspectionForm', InspectionFormScreen, 'New Inspection')}
    </InspectStack.Navigator>
  );
}

// Stack navigator for Chat tab
function ChatStackNavigator() {
  return (
    // @ts-ignore - React Navigation 7 Navigator id typing issue
    <ChatStack.Navigator screenOptions={{ headerStyle, headerTitleStyle }}>
      {createStackScreen(ChatStack, 'ChatScreen', ChatScreen, 'AI Advisor')}
    </ChatStack.Navigator>
  );
}

// Stack navigator for More tab
function MoreStackNavigator() {
  return (
    // @ts-ignore - React Navigation 7 Navigator id typing issue
    <MoreStack.Navigator screenOptions={{ headerStyle, headerTitleStyle }}>
      {createStackScreen(MoreStack, 'MoreScreen', MoreScreen, 'More')}
      {createStackScreen(MoreStack, 'ViewInspections', ViewInspectionsScreen, 'Inspection History')}
      {createStackScreen(MoreStack, 'HiveSharing', HiveSharingScreen, 'Hive Sharing')}
      {createStackScreen(MoreStack, 'Admin', AdminScreen, 'Admin Panel')}
    </MoreStack.Navigator>
  );
}

function MainTabNavigator() {
  return (
    // @ts-ignore - React Navigation 7 Navigator id typing issue
    <Tab.Navigator
      screenOptions={{
        tabBarStyle: { 
          backgroundColor: '#fbeee6',
          borderTopWidth: 1,
          borderTopColor: '#ddd',
        },
        tabBarActiveTintColor: '#a67c52',
        tabBarInactiveTintColor: '#6d4c1b',
        headerShown: false,
      }}
    >
      <Tab.Screen 
        name="Home" 
        component={HomeStackNavigator}
        options={{
          tabBarIcon: ({ focused }) => <TabBarIcon name="🏠" focused={focused} />,
        }}
      />
      <Tab.Screen 
        name="Inspect" 
        component={InspectStackNavigator}
        options={{
          tabBarLabel: 'Inspect',
          tabBarIcon: ({ focused }) => <TabBarIcon name="📝" focused={focused} />,
        }}
      />
      <Tab.Screen 
        name="Chat" 
        component={ChatStackNavigator}
        options={{
          tabBarLabel: 'AI Advisor',
          tabBarIcon: ({ focused }) => <TabBarIcon name="🤖" focused={focused} />,
        }}
      />
      <Tab.Screen 
        name="More" 
        component={MoreStackNavigator}
        options={{
          title: 'More',
          tabBarIcon: ({ focused }) => <TabBarIcon name="⋮" focused={focused} />,
        }}
      />
    </Tab.Navigator>
  );
}

// Loading component
function LoadingScreen() {
  return (
    <View style={styles.loadingContainer}>
      <ActivityIndicator size="large" color="#a67c52" />
      <Text style={styles.loadingText}>Loading...</Text>
    </View>
  );
}

export default function AppNavigator() {
  const { isAuthenticated, loading } = useAuth();
  
  // Show loading screen while checking auth
  if (loading) {
    return <LoadingScreen />;
  }

  return (
    // @ts-ignore - React Navigation 7 Navigator id typing issue
    <RootStack.Navigator screenOptions={{ headerShown: false }}>
      {isAuthenticated ? (
        <RootStack.Screen 
          name="MainTabs" 
          component={MainTabNavigator}
        />
      ) : (
        <RootStack.Screen 
          name="Login" 
          component={LoginScreen}
        />
      )}
    </RootStack.Navigator>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fbeee6',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#a67c52',
  },
});
