import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';

interface Tab {
  name: string;
  label: string;
  icon: string;
}

interface BottomTabBarProps {
  currentScreen: string;
  onNavigate: (screen: string) => void;
}

const TABS: Tab[] = [
  { name: 'home', label: 'Home', icon: '🏠' },
  { name: 'dashboard', label: 'Dashboard', icon: '📊' },
  { name: 'hives', label: 'Hives', icon: '🏠' },
  { name: 'inspect', label: 'Inspect', icon: '📝' },
  { name: 'chat', label: 'Chat', icon: '🤖' },
];

export default function BottomTabBar({ currentScreen, onNavigate }: BottomTabBarProps) {
  return (
    <View style={styles.container}>
      {TABS.map((tab) => {
        const isActive = currentScreen === tab.name;
        return (
          <TouchableOpacity
            key={tab.name}
            style={styles.tab}
            onPress={() => onNavigate(tab.name)}
          >
            <Text style={[styles.icon, isActive && styles.activeIcon]}>
              {tab.icon}
            </Text>
            <Text style={[styles.label, isActive && styles.activeLabel]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: '#fbeee6',
    borderTopWidth: 1,
    borderTopColor: '#ddd',
    paddingVertical: 8,
    paddingHorizontal: 16,
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    maxWidth: 560,
    alignSelf: 'center',
  },
  tab: {
    flexGrow: 1,
    flexBasis: 0,
    minWidth: 0,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
  },
  icon: {
    fontSize: 24,
    marginBottom: 4,
  },
  activeIcon: {
    opacity: 1,
  },
  label: {
    fontSize: 11,
    color: '#6d4c1b',
    textAlign: 'center',
  },
  activeLabel: {
    color: '#a67c52',
    fontWeight: '600',
  },
});

