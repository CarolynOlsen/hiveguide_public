import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService, Hive } from '../services/api';

interface HiveCardProps {
  hive: Hive;
  onEdit: (hive: Hive) => void;
  onDelete: (hive: Hive) => void;
}

const HiveCard = ({ hive, onEdit, onDelete }: HiveCardProps) => (
  <View style={styles.hiveCard}>
    <View style={styles.hiveHeader}>
      <Text style={styles.hiveName}>{hive.nickname}</Text>
      <Text style={styles.hiveDate}>{new Date(hive.created_at).toLocaleDateString()}</Text>
    </View>
    
    {hive.location && (
      <Text style={styles.hiveLocation}>📍 {hive.location}</Text>
    )}
    
    {hive.description && (
      <Text style={styles.hiveDescription}>{hive.description}</Text>
    )}
    
    <View style={styles.actionButtons}>
      <TouchableOpacity 
        style={[styles.actionButton, styles.editButton]} 
        onPress={() => onEdit(hive)}
      >
        <Text style={styles.buttonText}>Edit</Text>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.actionButton, styles.deleteButton]} 
        onPress={() => onDelete(hive)}
      >
        <Text style={[styles.buttonText, styles.deleteButtonText]}>Delete</Text>
      </TouchableOpacity>
    </View>
  </View>
);

export default function HivesScreen({ navigation }: { navigation: any }) {
  const queryClient = useQueryClient();

  // Fetch hives
  const { data: hives, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['hives'],
    queryFn: async () => {
      return await apiService.getHives();
    },
  });

  // Delete hive mutation
  const deleteMutation = useMutation({
    mutationFn: (hiveId: number) => apiService.deleteHive(hiveId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hives'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const handleEdit = (hive: Hive) => {
    navigation.navigate('EditHive', { hive });
  };

  const handleDelete = (hive: Hive) => {
    Alert.alert(
      'Delete Hive',
      `Are you sure you want to delete "${hive.nickname}"? This action cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteMutation.mutateAsync(hive.id);
              Alert.alert('Success', 'Hive deleted successfully');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete hive');
            }
          },
        },
      ]
    );
  };

  const handleAddHive = () => {
    navigation.navigate('AddHive');
  };

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#a67c52" />
        <Text style={styles.loadingText}>Loading hives...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Failed to load hives</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => refetch()}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!hives || hives.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.emptyStateTitle}>No hives yet!</Text>
        <Text style={styles.emptyStateText}>
          Add your first hive to start tracking inspections
        </Text>
        <TouchableOpacity style={styles.addButton} onPress={handleAddHive}>
          <Text style={styles.addButtonText}>Add Your First Hive</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={hives}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <HiveCard 
            hive={item} 
            onEdit={handleEdit} 
            onDelete={handleDelete} 
          />
        )}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl refreshing={isFetching} onRefresh={refetch} />
        }
      />
      
      <TouchableOpacity style={styles.floatingButton} onPress={handleAddHive}>
        <Text style={styles.floatingButtonText}>+</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff8f0',
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff8f0',
    padding: 24,
  },
  listContainer: {
    padding: 16,
    paddingBottom: 80, // Space for floating button
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
    marginBottom: 24,
  },
  addButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderRadius: 12,
  },
  addButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  hiveCard: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
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
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    flex: 1,
  },
  hiveDate: {
    fontSize: 12,
    color: '#888',
  },
  hiveLocation: {
    fontSize: 14,
    color: '#666',
    marginBottom: 8,
  },
  hiveDescription: {
    fontSize: 14,
    color: '#555',
    marginBottom: 16,
    lineHeight: 20,
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  actionButton: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  editButton: {
    backgroundColor: '#a67c52',
  },
  deleteButton: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#ff6b6b',
  },
  buttonText: {
    fontSize: 14,
    fontWeight: 'bold',
    color: 'white',
  },
  deleteButtonText: {
    color: '#ff6b6b',
  },
  floatingButton: {
    position: 'absolute',
    right: 16,
    bottom: 16,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#a67c52',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#a67c52',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  floatingButtonText: {
    fontSize: 24,
    color: 'white',
    fontWeight: 'bold',
  },
});