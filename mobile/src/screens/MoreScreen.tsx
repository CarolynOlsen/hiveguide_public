import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
} from 'react-native';
import { useAuth } from '../contexts/AuthContext';

interface MoreScreenProps {
  navigation: any;
}

interface MenuItem {
  id: string;
  title: string;
  subtitle: string;
  emoji: string;
  screen: string;
  adminOnly?: boolean;
}

const MENU_ITEMS: MenuItem[] = [
  {
    id: 'dashboard',
    title: 'Dashboard',
    subtitle: 'Overview of your apiaries and hives',
    emoji: '📊',
    screen: 'Dashboard',
  },
  {
    id: 'hives',
    title: 'My Hives',
    subtitle: 'Manage your hive collection',
    emoji: '🐝',
    screen: 'Hives',
  },
  {
    id: 'inspections',
    title: 'View Inspections',
    subtitle: 'Browse past inspection records',
    emoji: '📋',
    screen: 'ViewInspections',
  },
  {
    id: 'sharing',
    title: 'Hive Sharing',
    subtitle: 'Share hives with family and colleagues',
    emoji: '👥',
    screen: 'HiveSharing',
  },
  {
    id: 'admin',
    title: 'Admin Panel',
    subtitle: 'Manage users and system settings',
    emoji: '⚙️',
    screen: 'Admin',
    adminOnly: true,
  },
];

export default function MoreScreen({ navigation }: MoreScreenProps) {
  const { user } = useAuth();
  
  const visibleItems = MENU_ITEMS.filter(item => 
    !item.adminOnly || (user?.is_admin === true)
  );

  const handlePress = (screen: string) => {
    // Map screen names to their tab and screen combination
    const screenMap: { [key: string]: { tab: string; screen?: string } } = {
      'Dashboard': { tab: 'Home', screen: 'Dashboard' },
      'Hives': { tab: 'Home', screen: 'Hives' },
      'ViewInspections': { tab: 'More', screen: 'ViewInspections' },
      'HiveSharing': { tab: 'More', screen: 'HiveSharing' },
      'Admin': { tab: 'More', screen: 'Admin' },
    };

    const route = screenMap[screen];
    if (route) {
      if (route.screen) {
        // Navigate to specific screen in a tab
        navigation.navigate(route.tab, { screen: route.screen });
      } else {
        // Navigate to tab's initial screen
        navigation.navigate(route.tab);
      }
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView style={styles.scrollView}>
        <View style={styles.menuContainer}>
          {visibleItems.map((item) => (
            <TouchableOpacity
              key={item.id}
              style={styles.menuItem}
              onPress={() => handlePress(item.screen)}
            >
              <View style={styles.menuItemContent}>
                <Text style={styles.menuItemEmoji}>{item.emoji}</Text>
                <View style={styles.menuItemText}>
                  <Text style={styles.menuItemTitle}>{item.title}</Text>
                  <Text style={styles.menuItemSubtitle}>{item.subtitle}</Text>
                </View>
                <Text style={styles.chevron}>›</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Hive Guide v1.0 - Your intelligent beekeeping companion
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f6f0',
  },
  scrollView: {
    flex: 1,
  },
  menuContainer: {
    padding: 20,
  },
  menuItem: {
    backgroundColor: 'white',
    borderRadius: 12,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 1,
    },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  menuItemContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  menuItemEmoji: {
    fontSize: 24,
    marginRight: 16,
  },
  menuItemText: {
    flex: 1,
  },
  menuItemTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#2c2c2c',
    marginBottom: 4,
  },
  menuItemSubtitle: {
    fontSize: 14,
    color: '#666',
    lineHeight: 18,
  },
  chevron: {
    fontSize: 20,
    color: '#a67c52',
    fontWeight: 'bold',
  },
  footer: {
    padding: 20,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#999',
    textAlign: 'center',
  },
});