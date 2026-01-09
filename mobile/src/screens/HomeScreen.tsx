import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Modal,
  SafeAreaView,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';

// Navigation types
type RootStackParamList = {
  MainTabs: undefined;
  Dashboard: undefined;
  Inspect: undefined;
  Chat: undefined;
  Hives: undefined;
  Home: undefined;
};

type NavigationProp = StackNavigationProp<RootStackParamList>;

// Monthly beekeeping tips based on web app
const MONTHLY_TIPS = {
  0: { // January
    main: "Winter cluster management. Bees are in a tight cluster to maintain warmth, consuming 1-2 pounds of honey per day to keep internal temperature around 70°F.",
    details: [
      "Clear snow from hive entrance if present",
      "Emergency feeding with fondant patty if hives weigh less than 50-80 pounds",
      "Order bees and equipment for spring",
      "Check and repair beekeeping equipment",
      "On warm days (>50°F), bees may take cleansing flights"
    ]
  },
  1: { // February
    main: "Late winter monitoring. Bees continue clustering for warmth and may move around the hive to access honey stores.",
    details: [
      "Clear snow from hive entrance if present",
      "Emergency feeding with fondant patty if hives weigh less than 50-80 pounds",
      "Order bees and equipment for spring",
      "Check and repair beekeeping equipment",
      "On warm days (>50°F), bees may take cleansing flights"
    ]
  },
  2: { // March
    main: "Early spring awakening. Bees can starve during March due to low honey stores. Brood production increases, requiring more energy resources.",
    details: [
      "Check hive weight - bees can easily starve during this time",
      "Feed bees 1:1 sugar water syrup and pollen patty",
      "Remove winterizing gear when temperatures are consistently above freezing",
      "Get frame count on warm days (>55°F) - strong hives have 6+ frames with bees",
      "Change entrance reducer to larger size",
      "Test and treat for tracheal mites if suspected"
    ]
  },
  3: { // April
    main: "Spring buildup season. Brood increases rapidly with rising temperatures and pollen presence. Drones begin to be produced.",
    details: [
      "Full hive inspection on warm days (>55°F) - check all stages of brood",
      "Attempt to find the queen - populations are small and easier to spot",
      "Consider splitting overwintered hives to control population and reduce swarming risk",
      "Begin monthly check for foulbrood diseases",
      "Feed bees 1:1 sugar water syrup and pollen patty",
      "Register hives with Utah Department of Agriculture and Food (UDAF)"
    ]
  },
  4: { // May
    main: "Swarm season begins. Rapidly expanding bee populations can lead to swarming. Perform Varroa mite checks and treat if needed.",
    details: [
      "Full hive inspection - assess pollen and nectar stores",
      "Assess laying pattern and all stages of brood for queen health",
      "Do frame count to ensure populations are rising",
      "Feed 1:1 sugar water syrup to new colonies until nectar flow supports them",
      "Watch for and manage swarming behaviors - add boxes or split hives",
      "Add honey super when you have 7 full frames of capped honey in top box",
      "Varroa mite check - treat if more than 5 mites per 300 bees"
    ]
  },
  5: { // June
    main: "Peak nectar flow in Utah. Bees are busy foraging and bringing nectar back to the hive. Target 80-100 pounds of honey for winter stores.",
    details: [
      "Thorough hive inspection - assess laying pattern and all stages of brood",
      "Remove entrance reducer at beginning of month",
      "Watch for and manage swarming behaviors",
      "Add honey super when you have 7 full frames of capped honey in top box",
      "Move full and capped frames to outside of box to encourage filling empty frames"
    ]
  },
  6: { // July
    main: "High temperatures may cause bees to beard on outside of hive. Hive population at peak, making queen spotting difficult.",
    details: [
      "Full hive inspection - look for all stages of brood and capped nectar",
      "Ensure hive has access to water during hot, dry months",
      "Add honey super when you have 7 full frames of capped honey in top box",
      "If bees are bearding, improve ventilation with screened bottom board or prop lid open",
      "Continue to manage hive to prevent swarming",
      "Add supers as necessary"
    ]
  },
  7: { // August
    main: "Harvest season begins, and winter is coming. Established hives should have over 100 pounds of honey going into winter. Critical time for Varroa mite treatment.",
    details: [
      "Thorough hive inspection - assess laying pattern and queen strength",
      "Assess hive for brood diseases",
      "Check for Varroa mite - treat if more than 5 mites per 300 bees",
      "Begin honey harvest from supers if stores are abundant",
      "Don't over harvest - colony needs 100 pounds for winter stores"
    ]
  },
  8: { // September
    main: "Fall preparation begins. Hive slows down, bee populations diminish, and queen starts laying winter brood.",
    details: [
      "Thorough inspection - verify queen is laying",
      "Begin feeding 2:1 sugar water syrup with in-hive feeder",
      "Install robber screens or reduce entrance to discourage robbing",
      "Weigh hives - should be 80-100 pounds with 10-12 full deep frames of capped honey",
      "Continue monitoring and treating for Varroa mite"
    ]
  },
  9: { // October
    main: "Winter preparation intensifies. Bees are building population of overwintering bees with different physiology for cold temperatures.",
    details: [
      "Final full hive inspection if temperatures are warm",
      "Assess honey stores for winter, laying pattern and all stages of brood",
      "Feed 2:1 sugar water syrup until temperatures drop near freezing",
      "Wrap hives at high elevations or with little wind protection",
      "Ensure adequate air circulation to prevent condensation",
      "Change entrance reducer to smallest opening",
      "Install mouse guard and secure lid"
    ]
  },
  10: { // November
    main: "Deep winter management. Bees begin clustering at 57°F and shiver wing muscles to maintain hive temperature.",
    details: [
      "Be careful opening hive in cold temperatures",
      "If lifting lid is necessary, pick calm, warm day (>55°F) and work quickly",
      "Feed fondant patty if hive weight or honey stores are light",
      "Clear snow from hive entrance"
    ]
  },
  11: { // December
    main: "Minimal disturbance period. Bees should be disturbed as little as possible. Assess status by knocking on hive and listening for buzzing.",
    details: [
      "Feed fondant patty if hive weight or honey stores are light",
      "Clear snow from hive entrance",
      "Assess bee status by knocking on hive and listening for buzzing sound",
      "On warm days, bees may make quick cleansing flights"
    ]
  }
};

export default function HomeScreen() {
  const [tipsModalVisible, setTipsModalVisible] = useState(false);
  const navigation = useNavigation<NavigationProp>();

  // Get current month's tips
  const currentMonth = new Date().getMonth() as keyof typeof MONTHLY_TIPS;
  const monthlyTip = MONTHLY_TIPS[currentMonth];
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  // Helper to navigate to screens in other tab stacks
  const navigateTo = (screen: string) => {
    // Map screen names to their tab and screen combination
    const screenMap: { [key: string]: { tab: string; screen?: string } } = {
      'Dashboard': { tab: 'Home', screen: 'Dashboard' },
      'Hives': { tab: 'Home', screen: 'Hives' },
      'Inspect': { tab: 'Inspect' },
      'Chat': { tab: 'Chat' },
      'ChatScreen': { tab: 'Chat', screen: 'ChatScreen' },
    };

    const route = screenMap[screen];
    if (route) {
      if (route.screen) {
        // Navigate to specific screen in a tab
        navigation.navigate(route.tab as any, { screen: route.screen });
      } else {
        // Navigate to tab's initial screen
        navigation.navigate(route.tab as any);
      }
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.contentContainer}>
        {/* Hero Section */}
        <View style={styles.heroSection}>
          <Text style={styles.heroTitle}>
            Welcome to{'\n'}Hive Guide
          </Text>
          <Text style={styles.heroSubtitle}>
            Log inspections, get AI insights, and track your hive health with intelligent recommendations.
          </Text>
          <View style={styles.betaWarning}>
            <Text style={styles.betaWarningText}>
              ⚠️ Beta Version: This app is under active development. Please consider all data as temporary during this testing phase.
            </Text>
          </View>
          <TouchableOpacity 
            style={styles.ctaButton}
            onPress={() => navigateTo('Chat')}
          >
            <Text style={styles.ctaButtonText}>🤖 Ask Hive Guide</Text>
          </TouchableOpacity>
        </View>

        {/* Quick Actions */}
        <View style={styles.actionsSection}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.actionsGrid}>
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={() => navigateTo('Dashboard')}
            >
              <Text style={styles.actionIcon}>📊</Text>
              <Text style={styles.actionText}>Dashboard</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={() => navigateTo('Inspect')}
            >
              <Text style={styles.actionIcon}>📝</Text>
              <Text style={styles.actionText}>New Inspection</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={() => navigateTo('Hives')}
            >
              <Text style={styles.actionIcon}>🏠</Text>
              <Text style={styles.actionText}>My Hives</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={() => navigateTo('Chat')}
            >
              <Text style={styles.actionIcon}>🤖</Text>
              <Text style={styles.actionText}>AI Advisor</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Monthly Tips */}
        <View style={styles.tipsSection}>
          <Text style={styles.sectionTitle}>{monthNames[currentMonth]} Tips</Text>
          <View style={styles.tipCard}>
            <Text style={styles.tipText}>{monthlyTip.main}</Text>
            <TouchableOpacity
              style={styles.seeMoreButton}
              onPress={() => setTipsModalVisible(true)}
            >
              <Text style={styles.seeMoreText}>See more</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>

      {/* Tips Modal */}
      <Modal
        visible={tipsModalVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setTipsModalVisible(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>{monthNames[currentMonth]} Tips</Text>
            <TouchableOpacity
              style={styles.closeButton}
              onPress={() => setTipsModalVisible(false)}
            >
              <Text style={styles.closeButtonText}>Close</Text>
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.modalContent}>
            {monthlyTip.details.map((detail: string, index: number) => (
              <View key={index} style={styles.tipItem}>
                <Text style={styles.tipBullet}>•</Text>
                <Text style={styles.tipDetail}>{detail}</Text>
              </View>
            ))}
          </ScrollView>
          <View style={styles.modalActions}>
            <TouchableOpacity 
              style={styles.followUpButton}
              onPress={() => {
                setTipsModalVisible(false);
                navigateTo('Chat');
              }}
            >
              <Text style={styles.followUpButtonText}>Ask a follow-up</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff8f0',
  },
  scrollView: {
    flex: 1,
  },
  contentContainer: {
    padding: 20,
  },
  heroSection: {
    alignItems: 'center',
    marginBottom: 30,
    paddingVertical: 20,
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#a67c52',
    textAlign: 'center',
    marginBottom: 12,
  },
  heroSubtitle: {
    fontSize: 16,
    color: '#6d4c1b',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 16,
    paddingHorizontal: 10,
  },
  betaWarning: {
    backgroundColor: '#fff5f5',
    borderWidth: 1,
    borderColor: '#ffcccc',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginHorizontal: 10,
    marginBottom: 20,
  },
  betaWarningText: {
    fontSize: 13,
    color: '#d32f2f',
    textAlign: 'center',
    lineHeight: 18,
  },
  ctaButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 30,
    paddingVertical: 12,
    borderRadius: 25,
    shadowColor: '#a67c52',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 3,
  },
  ctaButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  actionsSection: {
    marginBottom: 30,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#a67c52',
    marginBottom: 15,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  actionButton: {
    backgroundColor: 'white',
    width: '48%',
    alignItems: 'center',
    padding: 20,
    borderRadius: 12,
    marginBottom: 10,
    shadowColor: '#a67c52',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  actionIcon: {
    fontSize: 24,
    marginBottom: 8,
  },
  actionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    textAlign: 'center',
  },
  tipsSection: {
    marginBottom: 20,
  },
  tipCard: {
    backgroundColor: 'white',
    padding: 20,
    borderRadius: 12,
    shadowColor: '#a67c52',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  tipText: {
    fontSize: 15,
    color: '#333',
    lineHeight: 22,
    marginBottom: 15,
  },
  seeMoreButton: {
    alignSelf: 'flex-start',
  },
  seeMoreText: {
    color: '#a67c52',
    fontSize: 14,
    fontWeight: '600',
  },
  modalContainer: {
    flex: 1,
    backgroundColor: '#fff8f0',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#e5d5c8',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#a67c52',
  },
  closeButton: {
    padding: 5,
  },
  closeButtonText: {
    color: '#a67c52',
    fontSize: 16,
    fontWeight: '600',
  },
  modalContent: {
    flex: 1,
    padding: 20,
  },
  tipItem: {
    flexDirection: 'row',
    marginBottom: 12,
    alignItems: 'flex-start',
  },
  tipBullet: {
    fontSize: 16,
    color: '#a67c52',
    marginRight: 10,
    marginTop: 2,
  },
  tipDetail: {
    flex: 1,
    fontSize: 15,
    color: '#333',
    lineHeight: 20,
  },
  modalActions: {
    padding: 20,
    borderTopWidth: 1,
    borderTopColor: '#e5d5c8',
  },
  followUpButton: {
    backgroundColor: '#a67c52',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
  },
  followUpButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
});