/**
 * Web-specific HomeScreen
 * Simplified version without React Navigation dependencies
 */
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
import { MONTHLY_TIPS, MONTH_NAMES } from '../../../shared/monthlyTips';

interface HomeScreenWebProps {
  navigation: {
    navigate: (screen: string) => void;
  };
}

export default function HomeScreenWeb({ navigation }: HomeScreenWebProps) {
  const [tipsModalVisible, setTipsModalVisible] = useState(false);

  // Get current month's tips
  const currentMonth = new Date().getMonth();
  const monthlyTip = MONTHLY_TIPS[currentMonth];

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
            onPress={() => navigation.navigate('chat')}
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
              onPress={() => navigation.navigate('dashboard')}
            >
              <Text style={styles.actionIcon}>📊</Text>
              <Text style={styles.actionText}>Dashboard</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={() => navigation.navigate('inspect')}
            >
              <Text style={styles.actionIcon}>📝</Text>
              <Text style={styles.actionText}>New Inspection</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={() => navigation.navigate('hives')}
            >
              <Text style={styles.actionIcon}>🏠</Text>
              <Text style={styles.actionText}>My Hives</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={styles.actionButton}
              onPress={() => navigation.navigate('chat')}
            >
              <Text style={styles.actionIcon}>🤖</Text>
              <Text style={styles.actionText}>AI Advisor</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Monthly Tips */}
        <View style={styles.tipsSection}>
          <Text style={styles.sectionTitle}>{MONTH_NAMES[currentMonth]} Tips</Text>
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
            <Text style={styles.modalTitle}>{MONTH_NAMES[currentMonth]} Tips</Text>
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
                navigation.navigate('chat');
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
