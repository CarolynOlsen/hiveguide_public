import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Alert,
  TextInput,
  Modal,
} from 'react-native';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService, Circle, CircleMembership } from '../services/api';

interface HiveSharingScreenProps {
  navigation: any;
}

interface CircleCardProps {
  circle: Circle;
  onEdit: (circle: Circle) => void;
  onDelete: (circle: Circle) => void;
}

const CircleCard = ({ circle, onEdit, onDelete }: CircleCardProps) => (
  <View style={styles.circleCard}>
    <View style={styles.cardHeader}>
      <View style={styles.cardTitleContainer}>
        <Text style={styles.circleName}>{circle.name}</Text>
        <Text style={styles.circleDate}>
          Created {new Date(circle.created_at).toLocaleDateString()}
        </Text>
      </View>
      <View style={styles.cardActions}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => onEdit(circle)}
        >
          <Text style={styles.actionButtonText}>👥</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionButton, styles.deleteButton]}
          onPress={() => onDelete(circle)}
        >
          <Text style={styles.actionButtonText}>🗑️</Text>
        </TouchableOpacity>
      </View>
    </View>
    
    {circle.description && (
      <Text style={styles.circleDescription}>{circle.description}</Text>
    )}
  </View>
);

export default function HiveSharingScreen({ navigation }: HiveSharingScreenProps) {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newCircleName, setNewCircleName] = useState('');
  const [newCircleDescription, setNewCircleDescription] = useState('');

  // Fetch circles
  const { data: circles, isLoading, error, refetch } = useQuery({
    queryKey: ['circles'],
    queryFn: async () => {
      return await apiService.getCircles();
    },
  });

  // Create circle mutation
  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) => 
      apiService.createCircle(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['circles'] });
      setShowCreateModal(false);
      setNewCircleName('');
      setNewCircleDescription('');
      Alert.alert('Success', 'Circle created successfully!');
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to create circle');
    },
  });

  // Delete circle mutation
  const deleteMutation = useMutation({
    mutationFn: (circleId: number) => apiService.deleteCircle(circleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['circles'] });
      Alert.alert('Success', 'Circle deleted successfully');
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to delete circle');
    },
  });

  const onRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const handleEdit = (circle: Circle) => {
    // Navigate to circle management screen
    Alert.alert(
      'Manage Circle',
      `Manage members and settings for "${circle.name}"`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Manage', onPress: () => {
          // TODO: Navigate to circle management screen
          Alert.alert('Feature Update', 'Circle member management coming in next update!');
        }}
      ]
    );
  };

  const handleDelete = (circle: Circle) => {
    Alert.alert(
      'Delete Circle',
      `Are you sure you want to delete "${circle.name}"? This will remove all members and cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => deleteMutation.mutate(circle.id),
        },
      ]
    );
  };

  const handleCreateCircle = () => {
    if (!newCircleName.trim()) {
      Alert.alert('Error', 'Please enter a circle name');
      return;
    }

    createMutation.mutate({
      name: newCircleName.trim(),
      description: newCircleDescription.trim() || undefined,
    });
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#a67c52" />
        <Text style={styles.loadingText}>Loading circles...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>Failed to load circles</Text>
        <TouchableOpacity style={styles.retryButton} onPress={() => refetch()}>
          <Text style={styles.retryButtonText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.headerActions}>
        <TouchableOpacity
          style={styles.createButton}
          onPress={() => setShowCreateModal(true)}
        >
          <Text style={styles.createButtonText}>+ Create Circle</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={circles}
        keyExtractor={(item) => item.id.toString()}
        renderItem={({ item }) => (
          <CircleCard
            circle={item}
            onEdit={handleEdit}
            onDelete={handleDelete}
          />
        )}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyEmoji}>👥</Text>
            <Text style={styles.emptyTitle}>No Circles Yet</Text>
            <Text style={styles.emptySubtitle}>
              Create a circle to share your hives with family or colleagues
            </Text>
            <TouchableOpacity
              style={styles.ctaButton}
              onPress={() => setShowCreateModal(true)}
            >
              <Text style={styles.ctaButtonText}>Create Your First Circle</Text>
            </TouchableOpacity>
          </View>
        }
      />

      {/* Create Circle Modal */}
      <Modal
        visible={showCreateModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowCreateModal(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowCreateModal(false)}>
              <Text style={styles.cancelButton}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Create Circle</Text>
            <TouchableOpacity
              onPress={handleCreateCircle}
              disabled={createMutation.isPending}
            >
              <Text style={[styles.saveButton, createMutation.isPending && styles.disabledButton]}>
                {createMutation.isPending ? 'Creating...' : 'Create'}
              </Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalContent}>
            <View style={styles.formGroup}>
              <Text style={styles.label}>Circle Name *</Text>
              <TextInput
                style={styles.input}
                value={newCircleName}
                onChangeText={setNewCircleName}
                placeholder="e.g., Family Hives, Work Apiary"
                placeholderTextColor="#999"
              />
            </View>

            <View style={styles.formGroup}>
              <Text style={styles.label}>Description</Text>
              <TextInput
                style={[styles.input, styles.textArea]}
                value={newCircleDescription}
                onChangeText={setNewCircleDescription}
                placeholder="Optional description..."
                placeholderTextColor="#999"
                multiline
                numberOfLines={3}
              />
            </View>
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f6f0',
  },
  headerActions: {
    padding: 16,
    backgroundColor: '#fbeee6',
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },
  createButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  createButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  listContainer: {
    padding: 16,
  },
  circleCard: {
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
  },
  cardTitleContainer: {
    flex: 1,
  },
  circleName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#2c2c2c',
    marginBottom: 4,
  },
  circleDate: {
    fontSize: 14,
    color: '#666',
  },
  circleDescription: {
    fontSize: 14,
    color: '#444',
    marginTop: 8,
    lineHeight: 20,
  },
  cardActions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#f0f0f0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  deleteButton: {
    backgroundColor: '#ffebee',
  },
  actionButtonText: {
    fontSize: 16,
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
  modalContainer: {
    flex: 1,
    backgroundColor: '#f8f6f0',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#fbeee6',
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#6d4c1b',
  },
  cancelButton: {
    fontSize: 16,
    color: '#666',
  },
  saveButton: {
    fontSize: 16,
    color: '#a67c52',
    fontWeight: '600',
  },
  disabledButton: {
    color: '#ccc',
  },
  modalContent: {
    flex: 1,
    padding: 20,
  },
  formGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    color: '#6d4c1b',
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    backgroundColor: 'white',
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
});