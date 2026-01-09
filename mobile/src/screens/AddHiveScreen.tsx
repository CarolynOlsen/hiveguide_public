import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  Image,
} from 'react-native';
import { useMutation } from '@tanstack/react-query';
import { apiService } from '../services/api';
import { Hive } from '@shared';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { launchImageLibrary, launchCamera, ImagePickerResponse, Asset } from 'react-native-image-picker';

export default function AddHiveScreen() {
  const [formData, setFormData] = useState({
    nickname: '',
    location: '',
    description: '',
  });
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [photoAsset, setPhotoAsset] = useState<Asset | null>(null);
  const navigation = useNavigation();

  // Create hive mutation
  const createHiveMutation = useMutation({
    mutationFn: (hiveData: {
      nickname: string;
      location?: string;
      description?: string;
      photoUri?: string;
      photoFileName?: string;
      photoType?: string;
    }) => apiService.createHiveWithPhoto(hiveData),
    onSuccess: (data) => {
      Alert.alert(
        'Success', 
        'Hive added successfully!',
        [
          {
            text: 'Add Another',
            onPress: () => {
              // Reset form
              setFormData({
                nickname: '',
                location: '',
                description: '',
              });
              setPhotoUri(null);
              setPhotoAsset(null);
            },
          },
          {
            text: 'Done',
            onPress: () => navigation.goBack(),
            style: 'default',
          },
        ]
      );
    },
    onError: (error) => {
      Alert.alert('Error', 'Failed to add hive. Please try again.');
      console.error('Add hive error:', error);
    },
  });

  const handleSubmit = () => {
    // Validation
    if (!formData.nickname.trim()) {
      Alert.alert('Error', 'Please enter a nickname for the hive.');
      return;
    }

    createHiveMutation.mutate({
      nickname: formData.nickname,
      location: formData.location,
      description: formData.description,
      photoUri: photoUri || undefined,
      photoFileName: photoAsset?.fileName || undefined,
      photoType: photoAsset?.type || undefined,
    });
  };

  const handlePhotoSelect = () => {
    Alert.alert(
      'Select Photo',
      'Choose photo source',
      [
        {
          text: 'Camera',
          onPress: () => launchCamera(
            {
              mediaType: 'photo',
              quality: 0.8,
              maxWidth: 1024,
              maxHeight: 1024,
            },
            handleImageResponse
          ),
        },
        {
          text: 'Photo Library',
          onPress: () => launchImageLibrary(
            {
              mediaType: 'photo',
              quality: 0.8,
              maxWidth: 1024,
              maxHeight: 1024,
            },
            handleImageResponse
          ),
        },
        {
          text: 'Cancel',
          style: 'cancel',
        },
      ]
    );
  };

  const handleImageResponse = (response: ImagePickerResponse) => {
    if (response.didCancel) {
      return;
    }
    if (response.errorCode) {
      Alert.alert('Error', response.errorMessage || 'Failed to select photo');
      return;
    }
    if (response.assets && response.assets.length > 0) {
      const asset = response.assets[0];
      setPhotoUri(asset.uri || null);
      setPhotoAsset(asset);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      <Text style={styles.title}>Add a New Hive</Text>
      
      {/* Nickname */}
      <View style={styles.formSection}>
        <Text style={styles.label}>
          Nickname <Text style={styles.required}>*</Text>
        </Text>
        <TextInput
          style={styles.textInput}
          value={formData.nickname}
          onChangeText={(text) => setFormData({ ...formData, nickname: text })}
          placeholder="e.g. Backyard Hive"
          placeholderTextColor="#999"
          autoCapitalize="words"
        />
      </View>

      {/* Photo */}
      <View style={styles.formSection}>
        <Text style={styles.label}>Photo</Text>
        <TouchableOpacity style={styles.photoButton} onPress={handlePhotoSelect}>
          {photoUri ? (
            <Image source={{ uri: photoUri }} style={styles.photoPreview} />
          ) : (
            <View style={styles.photoPlaceholder}>
              <Text style={styles.photoPlaceholderIcon}>📷</Text>
              <Text style={styles.photoPlaceholderText}>Add Photo</Text>
            </View>
          )}
        </TouchableOpacity>
      </View>

      {/* Location */}
      <View style={styles.formSection}>
        <Text style={styles.label}>Location</Text>
        <TextInput
          style={styles.textInput}
          value={formData.location}
          onChangeText={(text) => setFormData({ ...formData, location: text })}
          placeholder="e.g. North yard, rooftop, etc."
          placeholderTextColor="#999"
          autoCapitalize="words"
        />
      </View>

      {/* Description */}
      <View style={styles.formSection}>
        <Text style={styles.label}>Description</Text>
        <TextInput
          style={styles.textArea}
          value={formData.description}
          onChangeText={(text) => setFormData({ ...formData, description: text })}
          placeholder="Optional notes about this hive"
          placeholderTextColor="#999"
          multiline
          numberOfLines={4}
          textAlignVertical="top"
        />
      </View>

      {/* Buttons */}
      <View style={styles.buttonContainer}>
        <TouchableOpacity
          style={[styles.submitButton, styles.primaryButton]}
          onPress={handleSubmit}
          disabled={createHiveMutation.isPending}
        >
          {createHiveMutation.isPending ? (
            <ActivityIndicator color="white" size="small" />
          ) : (
            <Text style={styles.submitButtonText}>Add Hive</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.submitButton, styles.secondaryButton]}
          onPress={() => navigation.goBack()}
          disabled={createHiveMutation.isPending}
        >
          <Text style={styles.secondaryButtonText}>Cancel</Text>
        </TouchableOpacity>
      </View>
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
    paddingBottom: 32,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#a67c52',
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
  required: {
    color: 'red',
  },
  textInput: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  textArea: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    minHeight: 100,
  },
  photoButton: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 120,
  },
  photoPreview: {
    width: 100,
    height: 100,
    borderRadius: 8,
  },
  photoPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoPlaceholderIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  photoPlaceholderText: {
    fontSize: 16,
    color: '#666',
  },
  buttonContainer: {
    marginTop: 24,
    gap: 12,
  },
  submitButton: {
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  primaryButton: {
    backgroundColor: '#a67c52',
  },
  secondaryButton: {
    backgroundColor: '#eee',
    borderWidth: 1,
    borderColor: '#ddd',
  },
  submitButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  secondaryButtonText: {
    color: '#333',
    fontSize: 18,
    fontWeight: 'bold',
  },
});