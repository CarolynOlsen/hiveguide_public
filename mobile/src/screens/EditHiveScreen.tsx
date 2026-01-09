import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService, Hive } from '../services/api';

export default function EditHiveScreen({ navigation, route }: any) {
  const { hive } = route.params;
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState({
    nickname: hive.nickname,
    location: hive.location || '',
    description: hive.description || '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Hive>) => apiService.updateHive(hive.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hives'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      Alert.alert('Success', 'Hive updated successfully!', [
        { text: 'OK', onPress: () => navigation.goBack() }
      ]);
    },
    onError: (error: any) => {
      Alert.alert('Error', error.message || 'Failed to update hive');
    },
  });

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.nickname.trim()) {
      newErrors.nickname = 'Hive name is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validateForm()) {
      return;
    }

    updateMutation.mutate({
      nickname: formData.nickname.trim(),
      location: formData.location.trim() || null,
      description: formData.description.trim() || null,
    });
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.form}>
        <Text style={styles.title}>Edit Hive</Text>

        {/* Hive Name */}
        <View style={styles.formSection}>
          <Text style={styles.label}>Hive Name *</Text>
          <TextInput
            style={[styles.input, errors.nickname && styles.inputError]}
            value={formData.nickname}
            onChangeText={(text) => {
              setFormData({ ...formData, nickname: text });
              if (errors.nickname) {
                setErrors({ ...errors, nickname: '' });
              }
            }}
            placeholder="Enter hive name..."
            placeholderTextColor="#999"
          />
          {errors.nickname && <Text style={styles.errorText}>{errors.nickname}</Text>}
        </View>

        {/* Location */}
        <View style={styles.formSection}>
          <Text style={styles.label}>Location</Text>
          <TextInput
            style={styles.input}
            value={formData.location}
            onChangeText={(text) => setFormData({ ...formData, location: text })}
            placeholder="Enter location (optional)..."
            placeholderTextColor="#999"
          />
        </View>

        {/* Description */}
        <View style={styles.formSection}>
          <Text style={styles.label}>Description</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            value={formData.description}
            onChangeText={(text) => setFormData({ ...formData, description: text })}
            placeholder="Enter description (optional)..."
            placeholderTextColor="#999"
            multiline
            numberOfLines={4}
          />
        </View>

        {/* Submit Button */}
        <TouchableOpacity
          style={[styles.submitButton, updateMutation.isPending && styles.submitButtonDisabled]}
          onPress={handleSubmit}
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? (
            <ActivityIndicator size="small" color="white" />
          ) : (
            <Text style={styles.submitButtonText}>Update Hive</Text>
          )}
        </TouchableOpacity>

        {/* Cancel Button */}
        <TouchableOpacity
          style={styles.cancelButton}
          onPress={() => navigation.goBack()}
          disabled={updateMutation.isPending}
        >
          <Text style={styles.cancelButtonText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f6f0',
  },
  form: {
    padding: 20,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#6d4c1b',
    marginBottom: 24,
    textAlign: 'center',
  },
  formSection: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: 'bold',
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
  inputError: {
    borderColor: '#ff6b6b',
  },
  textArea: {
    minHeight: 100,
    textAlignVertical: 'top',
  },
  errorText: {
    color: '#ff6b6b',
    fontSize: 14,
    marginTop: 4,
  },
  submitButton: {
    backgroundColor: '#a67c52',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 20,
  },
  submitButtonDisabled: {
    backgroundColor: '#ccc',
  },
  submitButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  cancelButton: {
    backgroundColor: 'transparent',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 12,
  },
  cancelButtonText: {
    color: '#666',
    fontSize: 16,
  },
});