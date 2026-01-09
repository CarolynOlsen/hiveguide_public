import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  Platform,
  Image,
  Modal,
} from 'react-native';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiService } from '../services/api';
import { Hive, InspectionFormData } from '@shared';
// import AudioRecord from 'react-native-audio-record'; // Temporarily disabled to fix NativeEventEmitter error
import { launchImageLibrary, launchCamera, ImagePickerResponse, Asset } from 'react-native-image-picker';
import { useStreamingTranscription } from '../hooks/useStreamingTranscription';
import DateTimePicker from '@react-native-community/datetimepicker';

interface FormData extends InspectionFormData {
  hive_id: string;
  inspection_date?: string;
  transcription: string;
}

const INITIAL_FORM_STATE: FormData = {
  hive_id: '',
  inspection_date: new Date().toISOString().split('T')[0], // Default to today's date
  weather: '',
  temperature: '',
  brood_pattern: '',
  queen_seen: false,
  queen_cells: false,
  swarm_cells: false,
  honey_stores: '',
  pollen_stores: '',
  population: '',
  temperament: '',
  diseases_pests: '',
  treatments_applied: '',
  notes: '',
  transcription: '',
  queen_visible: false,
  eggs_visible: false,
  larvae_visible: false,
  capped_brood_visible: false,
  laying_pattern: '',
  activity_level: '',
};

const WEATHER_OPTIONS = [
  { value: 'sunny', label: 'Sunny', emoji: '☀️' },
  { value: 'cloudy', label: 'Cloudy', emoji: '☁️' },
  { value: 'partly_cloudy', label: 'Partly Cloudy', emoji: '⛅' },
  { value: 'rainy', label: 'Rainy', emoji: '🌧️' },
  { value: 'snowy', label: 'Snowy', emoji: '❄️' },
];

const TEMPERATURE_OPTIONS = [
  { value: 'under_60', label: 'Under 60°F', emoji: '❄️' },
  { value: '60s', label: '60s°F', emoji: '🧊' },
  { value: '70s', label: '70s°F', emoji: '🌤️' },
  { value: '80s', label: '80s°F', emoji: '☀️' },
  { value: '90_plus', label: '90+°F', emoji: '🔥' },
];

const SegmentedControl = ({ 
  options, 
  value, 
  onValueChange, 
  label 
}: { 
  options: Array<{value: string, label: string, emoji?: string}>, 
  value: string, 
  onValueChange: (value: string) => void,
  label: string 
}) => (
  <View style={styles.formSection}>
    <Text style={styles.label}>{label}</Text>
    <View style={styles.segmentedControl}>
      {options.map((option) => (
        <TouchableOpacity
          key={option.value}
          style={[
            styles.segmentButton,
            value === option.value && styles.segmentButtonActive
          ]}
          onPress={() => onValueChange(option.value)}
        >
          {option.emoji && (
            <Text style={styles.segmentButtonEmoji}>{option.emoji}</Text>
          )}
          <Text style={[
            styles.segmentButtonText,
            value === option.value && styles.segmentButtonTextActive
          ]}>
            {option.label}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  </View>
);

const Toggle = ({ 
  label, 
  value, 
  onValueChange 
}: { 
  label: string, 
  value: boolean, 
  onValueChange: (value: boolean) => void 
}) => (
  <TouchableOpacity
    style={styles.toggleRow}
    onPress={() => onValueChange(!value)}
  >
    <Text style={styles.toggleLabel}>{label}</Text>
    <View style={[styles.toggle, value && styles.toggleActive]}>
      <View style={[styles.toggleThumb, value && styles.toggleThumbActive]} />
    </View>
  </TouchableOpacity>
);

export default function InspectionFormScreen() {
  const [formData, setFormData] = useState<FormData>(INITIAL_FORM_STATE);

  const [showHiveDropdown, setShowHiveDropdown] = useState(false);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [photoAssets, setPhotoAssets] = useState<Asset[]>([]);

  // Platform-specific audio recording hooks
  // Use ref to track where transcription should start appending (avoids stale closure issues)
  const transcriptionStartNotesRef = useRef('');
  
  const {
    isStreaming,
    isConnecting,
    transcribedText,
    confidence,
    startStreaming,
    stopStreaming,
    isStreamingAvailable
  } = useStreamingTranscription({
    onTranscriptionUpdate: (text) => {
      // Show live transcription in notes field, appending to the notes from when recording started
      if (text && text.trim()) {
        const startNotes = transcriptionStartNotesRef.current;
        const separator = startNotes ? '\n\n' : '';
        setFormData(prev => ({
          ...prev,
          notes: startNotes + separator + text
        }));
      }
    },
    onFallbackNeeded: () => {
      // Fallback to regular recording - streaming not available
      console.log('Streaming not available, will use batch recording');
      setIsRecording(false);
    }
  });

  // On iOS, we use streaming transcription exclusively
  // On web/other platforms, streaming is not available so it will fall back gracefully

  // Initialize audio recording
  useEffect(() => {
    const audioConfig = {
      sampleRate: 16000,
      channels: 1,
      bitsPerSample: 16,
      audioSource: 6, // VOICE_RECOGNITION
      wavFile: 'audio_recording.wav'
    };
    // AudioRecord.init(audioConfig); // Temporarily disabled

    return () => {
      // AudioRecord.stop(); // Temporarily disabled
    };
  }, []);

  // Request microphone permission
  const requestMicrophonePermission = async () => {
    if (Platform.OS === 'android') {
      try {
        // Dynamic import for Android-only API (web-safe)
        const RN = await import('react-native');
        const granted = await RN.PermissionsAndroid.request(
          RN.PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
          {
            title: 'Microphone Permission',
            message: 'Hive Guide needs access to your microphone to record inspection notes.',
            buttonNeutral: 'Ask Me Later',
            buttonNegative: 'Cancel',
            buttonPositive: 'OK',
          }
        );
        return granted === RN.PermissionsAndroid.RESULTS.GRANTED;
      } catch (err) {
        console.warn(err);
        return false;
      }
    }
    
    // iOS: Actually request permission via native module
    if (Platform.OS === 'ios') {
      try {
          const AudioStreamingModule = (await import('../services/AudioStreamingModule')).default;
          const granted = await AudioStreamingModule.requestMicrophonePermission();
          return granted;
        } catch (error: any) {
          console.error('Failed to request microphone permission:', error);
          // Let the caller surface a single user-facing alert when permission is unavailable
          return false;
        }
    }
    
    // Web: Permissions handled by browser (navigator.mediaDevices.getUserMedia)
    return true;
  };

  // Audio recording functions - using streaming transcription
  const startRecording = async () => {
    console.log('=== startRecording called in InspectionFormScreen ===');
    try {
      const hasPermission = await requestMicrophonePermission();
      if (!hasPermission) {
        Alert.alert('Permission Required', 'Microphone access is required to record audio.');
        return;
      }

      // Save the current notes so we can append to them (use ref to avoid stale closure)
      transcriptionStartNotesRef.current = formData.notes;
      console.log('Starting recording with existing notes:', transcriptionStartNotesRef.current.substring(0, 50));

      // Call startStreaming and wait for it to succeed before setting isRecording
      console.log('Calling startStreaming...');
      await startStreaming();

      // Only set isRecording to true if startStreaming succeeded
      console.log('✅ startStreaming succeeded, setting isRecording = true');
      setIsRecording(true);
    } catch (error: any) {
      console.error('❌ Failed to start recording:', error);
      setIsRecording(false);

      // Show user-friendly error message
      const errorMsg = error?.message || 'Unknown error';
      Alert.alert('Recording Failed', `Could not start recording: ${errorMsg}`);
    }
  };

  const stopRecording = async () => {
    try {
      setIsRecording(false);
      await stopStreaming();
      console.log('Recording stopped, notes preserved');
    } catch (error) {
      console.error('Failed to stop recording:', error);
      setIsRecording(false);
      Alert.alert('Error', 'Failed to process recording');
    }
  };

  const transcribeAudio = async (audioFilePath: string) => {
    try {
      console.log('Transcribing audio file:', audioFilePath);
      
      const audioFormData = new FormData();
      audioFormData.append('audio', {
        uri: Platform.OS === 'ios' ? audioFilePath : `file://${audioFilePath}`,
        type: 'audio/wav',
        name: 'recording.wav',
      } as any);

      console.log('Sending transcription request...');
      const result = await apiService.transcribeAudio(audioFormData);
      console.log('Transcription result:', result);
      
      // Handle backend response format: { status: "success", transcription: "...", structured_data: {...} }
      if (result.status === 'success' && result.transcription) {
        const transcription = result.transcription || '';
        console.log('Transcription text:', transcription);
        console.log('Structured data:', result.structured_data);
        
        // Start with transcription and notes
        const newFormData: Partial<FormData> = {
          transcription,
          notes: formData.notes + (formData.notes ? '\n\n' : '') + transcription
        };

        // Apply structured data analysis if available
        if (result.structured_data) {
          const structuredData = result.structured_data;
          
          // Only update fields that have valid values
          if (structuredData.weather && ['sunny', 'cloudy', 'partly_cloudy', 'rainy', 'snowy'].includes(structuredData.weather)) {
            newFormData.weather = structuredData.weather;
          }
          if (structuredData.temperature && ['under_60', '60s', '70s', '80s', '90_plus'].includes(structuredData.temperature)) {
            newFormData.temperature = structuredData.temperature;
          }
          if (typeof structuredData.queen_visible === 'boolean') {
            newFormData.queen_visible = structuredData.queen_visible;
          }
          if (typeof structuredData.eggs_visible === 'boolean') {
            newFormData.eggs_visible = structuredData.eggs_visible;
          }
          if (typeof structuredData.larvae_visible === 'boolean') {
            newFormData.larvae_visible = structuredData.larvae_visible;
          }
          if (typeof structuredData.capped_brood_visible === 'boolean') {
            newFormData.capped_brood_visible = structuredData.capped_brood_visible;
          }
          if (structuredData.laying_pattern && ['poor', 'patchy', 'solid'].includes(structuredData.laying_pattern)) {
            newFormData.laying_pattern = structuredData.laying_pattern;
          }
          if (structuredData.activity_level && ['low', 'average', 'high'].includes(structuredData.activity_level)) {
            newFormData.activity_level = structuredData.activity_level;
          }
        }

        setFormData(prev => ({
          ...prev,
          ...newFormData
        }));

        const hasAnalyzedData = result.structured_data && Object.keys(result.structured_data).length > 0;
        Alert.alert(
          'Success', 
          hasAnalyzedData 
            ? 'Audio transcribed and form fields analyzed!' 
            : 'Audio transcribed successfully!'
        );
      } else {
        console.error('Transcription failed - unexpected response format:', result);
        const errorMsg = 'message' in result ? String(result.message) : 'Unexpected response format';
        Alert.alert('Error', `Failed to transcribe audio: ${errorMsg}`);
      }
    } catch (error) {
      console.error('Transcription failed with error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Network error';
      Alert.alert('Error', `Failed to transcribe audio: ${errorMessage}`);
    } finally {
      setTranscribing(false);
    }
  };

  // Analyze typed text function
  const analyzeTypedText = async () => {
    if (!formData.notes.trim()) {
      Alert.alert('No Text', 'Please enter some notes to analyze.');
      return;
    }

    setAnalyzing(true);
    try {
      console.log('Analyzing typed text:', formData.notes);
      
      // Use the analyze endpoint to process typed text
      const result = await apiService.analyzeText(formData.notes);
      console.log('Analysis result:', result);
      
      if (result.status === 'success' && result.structured_data) {
        const structuredData = result.structured_data;
        const newFormData: Partial<FormData> = {};
        
        // Only update fields that have valid values
        if (structuredData.weather && ['sunny', 'cloudy', 'partly_cloudy', 'rainy', 'snowy'].includes(structuredData.weather)) {
          newFormData.weather = structuredData.weather;
        }
        if (structuredData.temperature && ['under_60', '60s', '70s', '80s', '90_plus'].includes(structuredData.temperature)) {
          newFormData.temperature = structuredData.temperature;
        }
        if (typeof structuredData.queen_visible === 'boolean') {
          newFormData.queen_visible = structuredData.queen_visible;
        }
        if (typeof structuredData.eggs_visible === 'boolean') {
          newFormData.eggs_visible = structuredData.eggs_visible;
        }
        if (typeof structuredData.larvae_visible === 'boolean') {
          newFormData.larvae_visible = structuredData.larvae_visible;
        }
        if (typeof structuredData.capped_brood_visible === 'boolean') {
          newFormData.capped_brood_visible = structuredData.capped_brood_visible;
        }
        if (structuredData.laying_pattern && ['poor', 'patchy', 'solid'].includes(structuredData.laying_pattern)) {
          newFormData.laying_pattern = structuredData.laying_pattern;
        }
        if (structuredData.activity_level && ['low', 'average', 'high'].includes(structuredData.activity_level)) {
          newFormData.activity_level = structuredData.activity_level;
        }

        setFormData(prev => ({
          ...prev,
          ...newFormData
        }));

        const hasAnalyzedData = Object.keys(newFormData).length > 0;
        Alert.alert(
          'Analysis Complete', 
          hasAnalyzedData 
            ? 'Form fields updated based on your notes!' 
            : 'No specific inspection data detected in the text.'
        );
      } else {
        Alert.alert('Analysis Failed', 'Could not analyze the text. Please try again.');
      }
    } catch (error) {
      console.error('Text analysis failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Network error';
      Alert.alert('Error', `Failed to analyze text: ${errorMessage}`);
    } finally {
      setAnalyzing(false);
    }
  };

  // Photo picker handlers
  const handlePhotoSelect = () => {
    Alert.alert(
      'Select Photo',
      'Choose photo source',
      [
        {
          text: 'Camera',
          onPress: () => {
            launchCamera(
              {
                mediaType: 'photo',
                quality: 0.8,
                maxWidth: 1920,
                maxHeight: 1920,
              },
              handleImageResponse
            );
          },
        },
        {
          text: 'Photo Library',
          onPress: () => {
            launchImageLibrary(
              {
                mediaType: 'photo',
                quality: 0.8,
                maxWidth: 1920,
                maxHeight: 1920,
                selectionLimit: 5, // Allow multiple photos
              },
              handleImageResponse
            );
          },
        },
        {
          text: 'Cancel',
          style: 'cancel',
        },
      ],
      { cancelable: true }
    );
  };

  const handleImageResponse = (response: ImagePickerResponse) => {
    if (response.didCancel) {
      console.log('User cancelled image picker');
    } else if (response.errorCode) {
      console.log('ImagePicker Error: ', response.errorMessage);
      Alert.alert('Error', 'Failed to select image');
    } else if (response.assets && response.assets.length > 0) {
      setPhotoAssets([...photoAssets, ...response.assets]);
    }
  };

  const removePhoto = (index: number) => {
    setPhotoAssets(photoAssets.filter((_, i) => i !== index));
  };

  // Fetch hives
  const { data: hives = [], isLoading: hivesLoading, error: hivesError } = useQuery({
    queryKey: ['hives'],
    queryFn: async () => {
      const hivesData = await apiService.getHives();
      // Sort hives alphabetically by nickname (with null safety)
      return hivesData.sort((a: Hive, b: Hive) => {
        const nameA = a.nickname || '';
        const nameB = b.nickname || '';
        return nameA.localeCompare(nameB);
      });
    },
  });

  // Submit inspection
  const createInspectionMutation = useMutation({
    mutationFn: (data: FormData) => apiService.createInspection(Number(data.hive_id), data),
    onSuccess: () => {
      Alert.alert('Success', 'Inspection saved successfully!');
      // Reset form
      setFormData(INITIAL_FORM_STATE);
    },
    onError: (error) => {
      Alert.alert('Error', 'Failed to save inspection. Please try again.');
      console.error('Create inspection error:', error);
    },
  });

  const handleSubmit = async () => {
    // Validation
    if (!formData.hive_id) {
      Alert.alert('Error', 'Please select a hive.');
      return;
    }
    if (!formData.notes.trim()) {
      Alert.alert('Error', 'Please enter some inspection notes.');
      return;
    }

    // If we have photos, use FormData
    if (photoAssets.length > 0) {
      const submitFormData = new FormData();
      
      // Append all form fields
      Object.entries(formData).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          submitFormData.append(key, String(value));
        }
      });

      // Append photos
      photoAssets.forEach((asset, index) => {
        if (asset.uri && asset.type && asset.fileName) {
          submitFormData.append('photos', {
            uri: asset.uri,
            type: asset.type,
            name: asset.fileName,
          } as any);
        }
      });

      try {
        await apiService.createInspectionWithPhotos(Number(formData.hive_id), submitFormData);
        Alert.alert('Success', 'Inspection saved successfully!');
        // Reset form
        setFormData(INITIAL_FORM_STATE);
        setPhotoAssets([]);
      } catch (error) {
        Alert.alert('Error', 'Failed to save inspection. Please try again.');
        console.error('Create inspection error:', error);
      }
    } else {
      // No photos, use regular JSON submission
      createInspectionMutation.mutate(formData);
      setPhotoAssets([]);
    }
  };

  const selectedHive = hives.find((h: Hive) => h.id.toString() === formData.hive_id);

  if (hivesLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#a67c52" />
        <Text style={styles.loadingText}>Loading hives...</Text>
      </View>
    );
  }

  if (hives.length === 0) {
    return (
      <View style={styles.noHivesContainer}>
        <Text style={styles.noHivesTitle}>🐝 No Hives Found</Text>
        <Text style={styles.noHivesSubtitle}>Add a hive to get started!</Text>
        <TouchableOpacity style={styles.addHiveButton}>
          <Text style={styles.addHiveButtonText}>➕ Add Hive</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      
      <View style={styles.tipContainer}>
        <Text style={styles.tipText}>💡 <Text style={styles.tipBold}>Tip:</Text> Record or type your notes to document your inspection.</Text>
      </View>

      {/* Hive Selection */}
      <View style={[styles.formSection, styles.dropdownContainer]}>
        <Text style={styles.label}>Hive</Text>
        <TouchableOpacity
          style={styles.dropdown}
          onPress={() => setShowHiveDropdown(!showHiveDropdown)}
        >
          <Text style={styles.dropdownText}>
            {selectedHive ? selectedHive.nickname : 'Select a hive...'}
          </Text>
          <Text style={[styles.dropdownArrow, showHiveDropdown && styles.dropdownArrowOpen]}>▼</Text>
        </TouchableOpacity>
        
        {showHiveDropdown && (
          <View style={styles.dropdownList}>
            <ScrollView style={styles.dropdownScrollView} nestedScrollEnabled={true}>
              {hives.map((hive: Hive) => (
                <TouchableOpacity
                  key={hive.id}
                  style={styles.dropdownItem}
                  onPress={() => {
                    setFormData({ ...formData, hive_id: hive.id.toString() });
                    setShowHiveDropdown(false);
                  }}
                >
                  <Text style={styles.dropdownItemText}>{hive.nickname}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        )}
      </View>

      {/* Inspection Date */}
      <View style={styles.formSection}>
        <Text style={styles.label}>Inspection Date</Text>
        <TouchableOpacity
          style={styles.dateButton}
          onPress={() => setShowDatePicker(true)}
        >
          <Text style={styles.dateButtonText}>
            📅 {formData.inspection_date || 'Select date'}
          </Text>
        </TouchableOpacity>
        
        {/* iOS Date Picker with Modal */}
        {Platform.OS === 'ios' && showDatePicker && (
          <Modal
            transparent={true}
            animationType="slide"
            visible={showDatePicker}
            onRequestClose={() => setShowDatePicker(false)}
          >
            <View style={styles.modalOverlay}>
              <View style={styles.datePickerContainer}>
                <View style={styles.datePickerHeader}>
                  <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                    <Text style={styles.doneButton}>Done</Text>
                  </TouchableOpacity>
                </View>
                <DateTimePicker
                  value={formData.inspection_date ? new Date(formData.inspection_date) : new Date()}
                  mode="date"
                  display="spinner"
                  onChange={(event, selectedDate) => {
                    if (selectedDate) {
                      const dateString = selectedDate.toISOString().split('T')[0];
                      setFormData({ ...formData, inspection_date: dateString });
                    }
                  }}
                  maximumDate={new Date()}
                  style={styles.iosDatePicker}
                />
              </View>
            </View>
          </Modal>
        )}
        
        {/* Android Date Picker */}
        {Platform.OS === 'android' && showDatePicker && (
          <DateTimePicker
            value={formData.inspection_date ? new Date(formData.inspection_date) : new Date()}
            mode="date"
            display="default"
            onChange={(event, selectedDate) => {
              setShowDatePicker(false);
              if (selectedDate) {
                const dateString = selectedDate.toISOString().split('T')[0];
                setFormData({ ...formData, inspection_date: dateString });
              }
            }}
            maximumDate={new Date()}
          />
        )}
      </View>

      {/* Unified Notes Section */}
      <View style={styles.formSection}>
        <Text style={styles.label}>Inspection Notes</Text>
        <View style={styles.notesContainer}>
          <TextInput
            style={styles.textArea}
            value={formData.notes}
            onChangeText={(text) => setFormData({ ...formData, notes: text })}
            placeholder="Type your inspection notes or use voice recording below..."
            placeholderTextColor="#999"
            multiline
            numberOfLines={4}
          />
          
          <View style={styles.inputActionsContainer}>
            {/* Voice Recording Button with Streaming Transcription */}
            <TouchableOpacity
              style={[
                styles.actionButton,
                styles.recordButton,
                (isRecording || isStreaming || isConnecting) && styles.recordButtonActive
              ]}
              onPress={() => {
                console.log('🔴🔴🔴 RECORD BUTTON PRESSED 🔴🔴🔴');
                if (isRecording) {
                  stopRecording();
                } else {
                  startRecording();
                }
              }}
              disabled={isConnecting}
            >
              <Text style={styles.actionButtonEmoji}>
                {isConnecting ? '⏳' : (isRecording || isStreaming) ? '⏹️' : '🎤'}
              </Text>
              <Text style={[
                styles.actionButtonText, 
                (isRecording || isStreaming) && styles.recordButtonTextActive
              ]}>
                {isConnecting ? 'Connecting...' : (isRecording || isStreaming) ? 'Stop' : 'Record'}
              </Text>
            </TouchableOpacity>

            {/* Analyze Button */}
            <TouchableOpacity
              style={[
                styles.actionButton, 
                styles.analyzeButton,
                (!formData.notes.trim() || transcribing || analyzing || isStreaming || isRecording) && styles.actionButtonDisabled
              ]}
              onPress={analyzeTypedText}
              disabled={!formData.notes.trim() || transcribing || analyzing || isStreaming || isRecording}
            >
              <Text style={styles.actionButtonEmoji}>🧠</Text>
              <Text style={styles.actionButtonText}>
                {analyzing ? 'Analyzing...' : 'Analyze'}
              </Text>
            </TouchableOpacity>
          </View>

          {(transcribing || isStreaming || isConnecting) && (
            <View style={styles.transcribingContainer}>
              <ActivityIndicator size="small" color="#a67c52" />
              <Text style={styles.transcribingText}>
                {isConnecting ? 'Connecting...' :
                 isStreaming ? `🎤 Listening... ${confidence > 0 ? `(${Math.round(confidence * 100)}% confident)` : ''}` : 
                 isRecording ? 'Recording...' : 'Processing audio...'}
              </Text>
            </View>
          )}
          
        </View>
      </View>

      {/* Weather */}
      <SegmentedControl
        label="Weather"
        options={WEATHER_OPTIONS}
        value={formData.weather}
        onValueChange={(weather) => setFormData({ ...formData, weather })}
      />

      {/* Temperature */}
      <SegmentedControl
        label="Temperature"
        options={TEMPERATURE_OPTIONS}
        value={formData.temperature}
        onValueChange={(temperature) => setFormData({ ...formData, temperature })}
      />

      {/* Visibility Toggles */}
      <View style={styles.formSection}>
        <Text style={styles.label}>Brood & Queen</Text>
        <View style={styles.toggleContainer}>
          <Toggle
            label="Queen Visible"
            value={formData.queen_visible ?? false}
            onValueChange={(value) => setFormData({ ...formData, queen_visible: value })}
          />
          <Toggle
            label="Eggs Visible"
            value={formData.eggs_visible ?? false}
            onValueChange={(value) => setFormData({ ...formData, eggs_visible: value })}
          />
          <Toggle
            label="Larvae Visible"
            value={formData.larvae_visible ?? false}
            onValueChange={(value) => setFormData({ ...formData, larvae_visible: value })}
          />
          <Toggle
            label="Capped Brood Visible"
            value={formData.capped_brood_visible ?? false}
            onValueChange={(value) => setFormData({ ...formData, capped_brood_visible: value })}
          />
        </View>
      </View>

      {/* Laying Pattern */}
      <SegmentedControl
        label="Laying Pattern"
        options={[
          { value: 'poor', label: 'Poor', emoji: '😔' },
          { value: 'patchy', label: 'Patchy', emoji: '😐' },
          { value: 'solid', label: 'Solid', emoji: '😊' }
        ]}
        value={formData.laying_pattern ?? ''}
        onValueChange={(laying_pattern) => setFormData({ ...formData, laying_pattern })}
      />

      {/* Activity Level */}
      <SegmentedControl
        label="Activity Level"
        options={[
          { value: 'low', label: 'Low', emoji: '😴' },
          { value: 'average', label: 'Average', emoji: '🙂' },
          { value: 'high', label: 'High', emoji: '🏃‍♀️' }
        ]}
        value={formData.activity_level ?? ''}
        onValueChange={(activity_level) => setFormData({ ...formData, activity_level })}
      />

      {/* Photo Upload Section */}
      <View style={styles.formSection}>
        <Text style={styles.label}>Inspection Photos (Optional)</Text>
        <TouchableOpacity
          style={styles.photoButton}
          onPress={handlePhotoSelect}
        >
          <Text style={styles.photoButtonText}>📷 Add Photos</Text>
        </TouchableOpacity>
        
        {photoAssets.length > 0 && (
          <View style={styles.photoPreviewContainer}>
            {photoAssets.map((asset, index) => (
              <View key={index} style={styles.photoPreview}>
                <Image
                  source={{ uri: asset.uri }}
                  style={styles.photoPreviewImage}
                />
                <TouchableOpacity
                  style={styles.photoRemoveButton}
                  onPress={() => removePhoto(index)}
                >
                  <Text style={styles.photoRemoveText}>✕</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* Submit Button */}
      <TouchableOpacity
        style={[
          styles.submitButton,
          createInspectionMutation.isPending && styles.submitButtonDisabled
        ]}
        onPress={handleSubmit}
        disabled={createInspectionMutation.isPending}
      >
        {createInspectionMutation.isPending ? (
          <ActivityIndicator color="white" size="small" />
        ) : (
          <Text style={styles.submitButtonText}>Save Inspection</Text>
        )}
      </TouchableOpacity>
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff8f0',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 16,
    color: '#6d4c1b',
  },
  noHivesContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff8f0',
    padding: 24,
  },
  noHivesTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#a67c52',
    marginBottom: 8,
  },
  noHivesSubtitle: {
    fontSize: 16,
    color: '#6d4c1b',
    textAlign: 'center',
    marginBottom: 24,
  },
  addHiveButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  addHiveButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#a67c52',
    marginBottom: 16,
    textAlign: 'center',
  },
  tipContainer: {
    backgroundColor: '#e8f4f8',
    padding: 12,
    borderRadius: 8,
    marginBottom: 24,
    borderLeftWidth: 4,
    borderLeftColor: '#a67c52',
  },
  tipText: {
    fontSize: 14,
    color: '#6d4c1b',
  },
  tipBold: {
    fontWeight: 'bold',
  },
  formSection: {
    marginBottom: 24,
  },
  dropdownContainer: {
    position: 'relative',
    zIndex: 100,
  },
  label: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#6d4c1b',
    marginBottom: 8,
  },
  dropdown: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  dropdownText: {
    fontSize: 16,
    color: '#333',
  },
  dropdownArrow: {
    fontSize: 12,
    color: '#666',
    transform: [{ rotate: '0deg' }],
  },
  dropdownArrowOpen: {
    transform: [{ rotate: '180deg' }],
  },
  dropdownList: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ddd',
    borderTopWidth: 0,
    borderBottomLeftRadius: 8,
    borderBottomRightRadius: 8,
    maxHeight: 200,
    zIndex: 1000,
    elevation: 5,
  },
  dropdownScrollView: {
    maxHeight: 200,
  },
  dropdownItem: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  dropdownItemText: {
    fontSize: 16,
    color: '#333',
  },
  dateButton: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
  },
  dateButtonText: {
    fontSize: 16,
    color: '#333',
  },
  textArea: {
    backgroundColor: 'white',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    textAlignVertical: 'top',
    minHeight: 100,
  },
  segmentedControl: {
    flexDirection: 'row',
    backgroundColor: '#f0f0f0',
    borderRadius: 8,
    overflow: 'hidden',
    flexWrap: 'wrap',
  },
  segmentButton: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 6,
    alignItems: 'center',
    backgroundColor: '#f0f0f0',
    minWidth: 70,
  },
  segmentButtonActive: {
    backgroundColor: '#a67c52',
  },
  segmentButtonEmoji: {
    fontSize: 18,
    marginBottom: 2,
  },
  segmentButtonText: {
    fontSize: 12,
    color: '#666',
    textAlign: 'center',
  },
  segmentButtonTextActive: {
    color: 'white',
    fontWeight: 'bold',
  },
  toggleContainer: {
    gap: 8,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: 'white',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ddd',
  },
  toggleLabel: {
    fontSize: 16,
    color: '#333',
  },
  toggle: {
    width: 50,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#ddd',
    justifyContent: 'center',
  },
  toggleActive: {
    backgroundColor: '#a67c52',
  },
  toggleThumb: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: 'white',
    marginLeft: 2,
  },
  toggleThumbActive: {
    marginLeft: 22,
  },
  submitButton: {
    backgroundColor: '#a67c52',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 24,
  },
  submitButtonDisabled: {
    backgroundColor: '#ccc',
  },
  submitButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  recordButton: {
    backgroundColor: '#f0f0f0',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  recordButtonActive: {
    backgroundColor: '#ffebee',
    borderColor: '#f44336',
  },
  recordButtonEmoji: {
    fontSize: 20,
    marginRight: 8,
  },
  recordButtonText: {
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
  },
  recordButtonTextActive: {
    color: '#f44336',
  },
  transcribingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
  },
  transcribingText: {
    fontSize: 14,
    color: '#6d4c1b',
    marginLeft: 8,
  },
  notesContainer: {
    backgroundColor: '#fff',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ddd',
    padding: 12,
  },
  inputActionsContainer: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 12,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ddd',
    backgroundColor: '#f0f0f0',
  },
  actionButtonEmoji: {
    fontSize: 16,
    marginRight: 6,
  },
  actionButtonText: {
    fontSize: 14,
    color: '#333',
    fontWeight: '500',
  },
  analyzeButton: {
    backgroundColor: '#e8f5e8',
    borderColor: '#4CAF50',
  },
  actionButtonDisabled: {
    backgroundColor: '#f5f5f5',
    borderColor: '#ccc',
    opacity: 0.6,
  },
  streamButton: {
    backgroundColor: '#e3f2fd',
    borderColor: '#2196F3',
  },
  streamButtonActive: {
    backgroundColor: '#bbdefb',
    borderColor: '#1976D2',
  },
  streamButtonTextActive: {
    color: '#1976D2',
    fontWeight: 'bold',
  },
  photoButton: {
    backgroundColor: '#f0f0f0',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  photoButtonText: {
    fontSize: 16,
    color: '#333',
    fontWeight: '500',
  },
  photoPreviewContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  photoPreview: {
    width: 100,
    height: 100,
    borderRadius: 8,
    overflow: 'hidden',
    position: 'relative',
  },
  photoPreviewImage: {
    width: '100%',
    height: '100%',
  },
  photoRemoveButton: {
    position: 'absolute',
    top: 4,
    right: 4,
    backgroundColor: 'rgba(255, 0, 0, 0.8)',
    borderRadius: 12,
    width: 24,
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoRemoveText: {
    color: 'white',
    fontSize: 14,
    fontWeight: 'bold',
  },
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  datePickerContainer: {
    backgroundColor: 'white',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingBottom: 20,
  },
  datePickerHeader: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  doneButton: {
    fontSize: 17,
    color: '#a67c52',
    fontWeight: '600',
  },
  iosDatePicker: {
    width: '100%',
    height: 216,
  },
});
