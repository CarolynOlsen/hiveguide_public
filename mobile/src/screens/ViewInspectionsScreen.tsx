import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  SafeAreaView,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { apiService, Inspection, Hive } from '../services/api';

interface ViewInspectionsScreenProps {
  navigation: any;
}

interface InspectionWithHive extends Inspection {
  hive?: Hive;
}

const InspectionCard = ({ inspection }: { inspection: InspectionWithHive }) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  return (
    <View style={styles.inspectionCard}>
      <View style={styles.cardHeader}>
        <View>
          <Text style={styles.hiveName}>
            {inspection.hive?.nickname || `Hive #${inspection.hive_id}`}
          </Text>
          <Text style={styles.inspectionDate}>
            {formatDate(inspection.inspection_date || inspection.created_at)} at {formatTime(inspection.inspection_date || inspection.created_at)}
          </Text>
        </View>
        <View style={styles.weatherContainer}>
          {inspection.weather && (
            <Text style={styles.weatherText}>
              {inspection.weather === 'sunny' && '☀️'}
              {inspection.weather === 'cloudy' && '☁️'}
              {inspection.weather === 'partly_cloudy' && '⛅'}
              {inspection.weather === 'rainy' && '🌧️'}
              {inspection.weather === 'snowy' && '❄️'}
            </Text>
          )}
          {inspection.temperature && (
            <Text style={styles.tempText}>{inspection.temperature}</Text>
          )}
        </View>
      </View>

      {inspection.notes && (
        <Text style={styles.inspectionNotes} numberOfLines={3}>
          {inspection.notes}
        </Text>
      )}

      <View style={styles.cardFooter}>
        {inspection.queen_visible && (
          <View style={styles.indicator}>
            <Text style={styles.indicatorEmoji}>👑</Text>
            <Text style={styles.indicatorText}>Queen</Text>
          </View>
        )}
        {inspection.eggs_visible && (
          <View style={styles.indicator}>
            <Text style={styles.indicatorEmoji}>🥚</Text>
            <Text style={styles.indicatorText}>Eggs</Text>
          </View>
        )}
        {inspection.larvae_visible && (
          <View style={styles.indicator}>
            <Text style={styles.indicatorEmoji}>🐛</Text>
            <Text style={styles.indicatorText}>Larvae</Text>
          </View>
        )}
        {inspection.activity_level && (
          <View style={styles.indicator}>
            <Text style={styles.indicatorEmoji}>
              {inspection.activity_level === 'high' && '🏃‍♀️'}
              {inspection.activity_level === 'average' && '🙂'}
              {inspection.activity_level === 'low' && '😴'}
            </Text>
            <Text style={styles.indicatorText}>
              {inspection.activity_level.charAt(0).toUpperCase() + inspection.activity_level.slice(1)}
            </Text>
          </View>
        )}
      </View>
    </View>
  );
};

export default function ViewInspectionsScreen({ navigation }: ViewInspectionsScreenProps) {
  const [refreshing, setRefreshing] = useState(false);

  // Fetch inspections
  const { data: inspections, isLoading, error, refetch } = useQuery({
    queryKey: ['inspections'],
    queryFn: async () => {
      return await apiService.getInspections();
    },
  });

  // Fetch hives for hive names
  const { data: hives } = useQuery({
    queryKey: ['hives'],
    queryFn: async () => {
      return await apiService.getHives();
    },
  });

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  // Merge hive data with inspections
  const inspectionsWithHives = inspections?.map(inspection => ({
    ...inspection,
    hive: hives?.find(hive => hive.id === inspection.hive_id)
  })) || [];

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#a67c52" />
        <Text style={styles.loadingText}>Loading inspections...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>Failed to load inspections</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => refetch()}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={inspectionsWithHives}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => <InspectionCard inspection={item} />}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyEmoji}>📋</Text>
            <Text style={styles.emptyTitle}>No Inspections Yet</Text>
            <Text style={styles.emptySubtitle}>
              Start by creating your first hive inspection!
            </Text>
            <TouchableOpacity
              style={styles.ctaButton}
              onPress={() => navigation.navigate('Inspect')}
            >
              <Text style={styles.ctaButtonText}>New Inspection</Text>
            </TouchableOpacity>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f6f0',
  },
  listContainer: {
    padding: 16,
  },
  inspectionCard: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
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
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  hiveName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#2c2c2c',
    marginBottom: 4,
  },
  inspectionDate: {
    fontSize: 14,
    color: '#666',
  },
  weatherContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  weatherText: {
    fontSize: 20,
  },
  tempText: {
    fontSize: 12,
    color: '#666',
    fontWeight: '500',
  },
  inspectionNotes: {
    fontSize: 14,
    color: '#444',
    lineHeight: 20,
    marginBottom: 12,
  },
  cardFooter: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  indicator: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f0f0f0',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  indicatorEmoji: {
    fontSize: 12,
    marginRight: 4,
  },
  indicatorText: {
    fontSize: 11,
    color: '#666',
    fontWeight: '500',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f8f6f0',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#6d4c1b',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f8f6f0',
    padding: 20,
  },
  errorText: {
    fontSize: 16,
    color: '#d32f2f',
    marginBottom: 16,
    textAlign: 'center',
  },
  retryButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    padding: 40,
  },
  emptyEmoji: {
    fontSize: 48,
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#6d4c1b',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#8b6914',
    textAlign: 'center',
    marginBottom: 24,
  },
  ctaButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  ctaButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
});