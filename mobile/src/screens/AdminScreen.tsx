import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService, PendingUser } from '../services/api';

interface AdminScreenProps {
  navigation: any;
}

interface UserCardProps {
  user: PendingUser;
  onApprove: (userId: number) => void;
  onReject: (userId: number) => void;
}

const UserCard = ({ user, onApprove, onReject }: UserCardProps) => (
  <View style={styles.userCard}>
    <View style={styles.userInfo}>
      <Text style={styles.userEmail}>{user.email}</Text>
      <Text style={styles.userDate}>
        Requested {new Date(user.created_at).toLocaleDateString()}
      </Text>
    </View>
    <View style={styles.userActions}>
      <TouchableOpacity
        style={[styles.actionButton, styles.approveButton]}
        onPress={() => onApprove(user.id)}
      >
        <Text style={styles.actionButtonText}>✓ Approve</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.actionButton, styles.rejectButton]}
        onPress={() => onReject(user.id)}
      >
        <Text style={styles.actionButtonText}>✗ Reject</Text>
      </TouchableOpacity>
    </View>
  </View>
);

export default function AdminScreen({ navigation }: AdminScreenProps) {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  // Fetch pending users
  const { data: pendingUsers, isLoading, error, refetch } = useQuery({
    queryKey: ['pendingUsers'],
    queryFn: async () => {
      return await apiService.getPendingUsers();
    },
  });

  // Approve user mutation
  const approveMutation = useMutation({
    mutationFn: (userId: number) => apiService.approveUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingUsers'] });
      Alert.alert('Success', 'User approved successfully!');
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to approve user');
    },
  });

  // Reject user mutation
  const rejectMutation = useMutation({
    mutationFn: (userId: number) => apiService.rejectUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingUsers'] });
      Alert.alert('Success', 'User rejected successfully');
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to reject user');
    },
  });

  const handleRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const handleApprove = (userId: number) => {
    Alert.alert(
      'Approve User',
      'Are you sure you want to approve this user?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Approve', onPress: () => approveMutation.mutate(userId) },
      ]
    );
  };

  const handleReject = (userId: number) => {
    Alert.alert(
      'Reject User',
      'Are you sure you want to reject this user? This will delete their account.',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Reject', 
          style: 'destructive',
          onPress: () => rejectMutation.mutate(userId) 
        },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      {isLoading && !refreshing ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#a67c52" />
          <Text style={styles.loadingText}>Loading pending users...</Text>
        </View>
      ) : error ? (
        <View style={styles.centerContainer}>
          <Text style={styles.errorText}>Failed to load pending users</Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => refetch()}>
            <Text style={styles.retryButtonText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.contentContainer}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor="#a67c52"
            />
          }
        >
          {!pendingUsers || pendingUsers.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyStateEmoji}>✓</Text>
              <Text style={styles.emptyStateTitle}>All Caught Up</Text>
              <Text style={styles.emptyStateText}>
                No pending user approvals at this time.
              </Text>
            </View>
          ) : (
            <>
              <Text style={styles.countText}>
                {pendingUsers.length} user{pendingUsers.length !== 1 ? 's' : ''} pending approval
              </Text>
              {pendingUsers.map((user) => (
                <UserCard
                  key={user.id}
                  user={user}
                  onApprove={handleApprove}
                  onReject={handleReject}
                />
              ))}
            </>
          )}
        </ScrollView>
      )}
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
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#6d4c1b',
  },
  errorText: {
    fontSize: 16,
    color: '#d32f2f',
    marginBottom: 20,
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
    fontWeight: '600',
  },
  contentContainer: {
    padding: 20,
  },
  countText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 16,
    textAlign: 'center',
  },
  userCard: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: 2,
    },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
  },
  userInfo: {
    marginBottom: 12,
  },
  userEmail: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  userDate: {
    fontSize: 14,
    color: '#666',
  },
  userActions: {
    flexDirection: 'row',
    gap: 10,
  },
  actionButton: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  approveButton: {
    backgroundColor: '#4caf50',
  },
  rejectButton: {
    backgroundColor: '#f44336',
  },
  actionButtonText: {
    color: 'white',
    fontSize: 14,
    fontWeight: '600',
  },
  emptyState: {
    alignItems: 'center',
    padding: 40,
    backgroundColor: 'white',
    borderRadius: 12,
    marginTop: 20,
  },
  emptyStateEmoji: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyStateTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#6d4c1b',
    marginBottom: 8,
  },
  emptyStateText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    lineHeight: 22,
  },
});