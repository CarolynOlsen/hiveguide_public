import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { apiService, DashboardData, HiveWithStatus } from '../services/api';

const getUrgencyIcon = (color: string) => {
  switch (color) {
    case 'red': return '🔴';
    case 'yellow': return '🟡';
    case 'green': return '🟢';
    default: return '⚪';
  }
};

const HiveCard = ({ hive }: { hive: HiveWithStatus }) => {
  const urgencyText = hive.days_since_inspection !== null 
    ? `${hive.days_since_inspection} days ago`
    : 'Never inspected';

  return (
    <View style={[styles.hiveCard, { borderLeftColor: hive.urgency_color }]}>
      <View style={styles.hiveHeader}>
        <Text style={styles.hiveName}>{hive.nickname}</Text>
        <Text style={styles.urgencyIcon}>{getUrgencyIcon(hive.urgency_color)}</Text>
      </View>
      {hive.location && (
        <Text style={styles.hiveLocation}>📍 {hive.location}</Text>
      )}
      <Text style={styles.inspectionDate}>Last inspection: {urgencyText}</Text>
      {hive.action_items.length > 0 && (
        <View style={styles.actionItems}>
          <Text style={styles.actionItemsHeader}>Action Items:</Text>
          {hive.action_items.slice(0, 2).map((item, index) => (
            <Text key={index} style={styles.actionItem}>• {item.description}</Text>
          ))}
          {hive.action_items.length > 2 && (
            <Text style={styles.moreItems}>+{hive.action_items.length - 2} more</Text>
          )}
        </View>
      )}
    </View>
  );
};

const ApiarySection = ({ location, hives }: { location: string; hives: HiveWithStatus[] }) => (
  <View style={styles.apiarySection}>
    <Text style={styles.apiaryHeader}>📍 {location || 'Unlocated Hives'}</Text>
    {hives.map((hive) => (
      <HiveCard key={hive.id} hive={hive} />
    ))}
  </View>
);

export default function DashboardScreen() {
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      return await apiService.getDashboardData();
    },
  });

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#a67c52" />
        <Text style={styles.loadingText}>Loading dashboard...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Failed to load dashboard</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => refetch()}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.emptyText}>No data available</Text>
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container}
      contentContainerStyle={styles.contentContainer}
      refreshControl={<RefreshControl refreshing={isFetching} onRefresh={refetch} />}
    >
      {/* Summary Stats */}
      <View style={styles.summaryContainer}>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{data.total_hives}</Text>
          <Text style={styles.statLabel}>Total Hives</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>{data.attention_count}</Text>
          <Text style={styles.statLabel}>Attention</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={[styles.statNumber, styles.urgentStat]}>{data.urgent_count}</Text>
          <Text style={styles.statLabel}>Urgent</Text>
        </View>
      </View>

      {/* Apiaries */}
      {Object.entries(data.apiaries).map(([location, hives]) => (
        <ApiarySection key={location} location={location} hives={hives} />
      ))}

      {Object.keys(data.apiaries).length === 0 && (
        <View style={styles.emptyState}>
          <Text style={styles.emptyStateTitle}>No hives yet!</Text>
          <Text style={styles.emptyStateText}>
            Add your first hive to start tracking inspections
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff8f0',
  },
  contentContainer: {
    padding: 16,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff8f0',
    padding: 24,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#6d4c1b',
  },
  errorText: {
    fontSize: 18,
    color: '#ff6b6b',
    textAlign: 'center',
    marginBottom: 16,
  },
  emptyText: {
    fontSize: 18,
    color: '#6d4c1b',
    textAlign: 'center',
  },
  retryButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  summaryContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    backgroundColor: 'white',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginHorizontal: 4,
    shadowColor: '#a67c52',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  statNumber: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#a67c52',
  },
  urgentStat: {
    color: '#ff6b6b',
  },
  statLabel: {
    fontSize: 12,
    color: '#6d4c1b',
    textAlign: 'center',
    marginTop: 4,
  },
  apiarySection: {
    marginBottom: 24,
  },
  apiaryHeader: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#a67c52',
    marginBottom: 12,
  },
  hiveCard: {
    backgroundColor: 'white',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    borderLeftWidth: 4,
    shadowColor: '#a67c52',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  hiveHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  hiveName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
    flex: 1,
  },
  urgencyIcon: {
    fontSize: 20,
  },
  hiveLocation: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  inspectionDate: {
    fontSize: 12,
    color: '#888',
    marginBottom: 8,
  },
  actionItems: {
    marginTop: 8,
  },
  actionItemsHeader: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#a67c52',
    marginBottom: 4,
  },
  actionItem: {
    fontSize: 11,
    color: '#666',
    marginBottom: 2,
  },
  moreItems: {
    fontSize: 11,
    color: '#a67c52',
    fontStyle: 'italic',
  },
  emptyState: {
    alignItems: 'center',
    padding: 32,
    marginTop: 32,
  },
  emptyStateTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#a67c52',
    marginBottom: 8,
  },
  emptyStateText: {
    fontSize: 16,
    color: '#6d4c1b',
    textAlign: 'center',
  },
});