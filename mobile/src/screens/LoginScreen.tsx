import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useController, useForm } from 'react-hook-form';
import { useAuth } from '../contexts/AuthContext';

interface LoginFormData {
  email: string;
  password: string;
}

interface LoginScreenProps {
  navigation: any; // In a real app, you'd type this properly
}

interface ControlledInputProps {
  name: keyof LoginFormData;
  control: any;
  placeholder: string;
  secureTextEntry?: boolean;
  keyboardType?: 'default' | 'email-address';
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
}

const ControlledInput = ({ 
  name, 
  control, 
  placeholder, 
  secureTextEntry = false, 
  keyboardType = 'default',
  autoCapitalize = 'none' 
}: ControlledInputProps) => {
  const { field, fieldState } = useController({
    control,
    defaultValue: '',
    name,
    rules: {
      required: `${name} is required`,
      ...(name === 'email' && {
        pattern: {
          value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
          message: 'Invalid email address',
        },
      }),
    },
  });

  return (
    <View style={styles.inputContainer}>
      <TextInput
        style={[styles.input, fieldState.error && styles.inputError]}
        placeholder={placeholder}
        placeholderTextColor="#999"
        value={field.value}
        onChangeText={field.onChange}
        onBlur={field.onBlur}
        secureTextEntry={secureTextEntry}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        autoCorrect={false}
      />
      {fieldState.error && <Text style={styles.errorText}>{fieldState.error.message}</Text>}
    </View>
  );
};

export default function LoginScreen({ navigation }: LoginScreenProps) {
  const [showRegister, setShowRegister] = useState(false);
  const [registerSuccess, setRegisterSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { signIn, signUp } = useAuth();

  const { control, handleSubmit, reset } = useForm<LoginFormData>();

  const onLogin = async (data: LoginFormData) => {
    setLoading(true);
    setError('');
    console.log('Attempting login with:', data); // DEBUG
    
    try {
      const result = await signIn(data.email, data.password);
      console.log('Login result:', result); // DEBUG
      console.log('Login result error:', result.error); // DEBUG
      
      if (!result.success) {
        // Show full error details on screen for debugging
        const errorMsg = result.error || 'Login failed (no error message)';
        console.log('Setting error message:', errorMsg);
        setError(errorMsg);
      }
      // If successful, AuthContext will handle navigation via state change
    } catch (err) {
      console.error('Login error caught in component:', err); // DEBUG
      setError('Login failed. Exception: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  };

  const onRegister = async (data: LoginFormData) => {
    setLoading(true);
    setError('');
    setRegisterSuccess(false);
    
    try {
      const result = await signUp(data.email, data.password);
      
      if (result.success) {
        setRegisterSuccess(true);
        setShowRegister(false);
        reset();
        Alert.alert(
          'Registration Successful',
          'Your account has been created and is pending admin approval. You will be notified when approved.',
          [{ text: 'OK' }]
        );
      } else {
        setError(result.error || 'Registration failed');
      }
    } catch (err) {
      setError('Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setShowRegister(!showRegister);
    setError('');
    setRegisterSuccess(false);
    reset();
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container} 
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.title}>Hive Guide</Text>
          <Text style={styles.subtitle}>Modern Beekeeping Assistant</Text>
          
          <View style={styles.form}>
            <ControlledInput
              name="email"
              control={control}
              placeholder="Email"
              keyboardType="email-address"
              autoCapitalize="none"
            />
            
            <ControlledInput
              name="password"
              control={control}
              placeholder="Password"
              secureTextEntry
            />
            
            {error ? <Text style={styles.errorText}>{error}</Text> : null}
            
            <TouchableOpacity
              style={[styles.button, loading && styles.buttonDisabled]}
              onPress={handleSubmit(showRegister ? onRegister : onLogin)}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>
                  {showRegister ? 'Register' : 'Login'}
                </Text>
              )}
            </TouchableOpacity>
            
            <TouchableOpacity
              style={styles.linkButton}
              onPress={toggleMode}
              disabled={loading}
            >
              <Text style={styles.linkText}>
                {showRegister 
                  ? 'Already have an account? Login' 
                  : "Don't have an account? Register"
                }
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff8f0',
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  card: {
    backgroundColor: 'white',
    borderRadius: 16,
    padding: 24,
    shadowColor: '#a67c52',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 5,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#a67c52',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#6d4c1b',
    textAlign: 'center',
    marginBottom: 32,
  },
  form: {
    gap: 16,
  },
  inputContainer: {
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  inputError: {
    borderColor: '#ff6b6b',
  },
  button: {
    backgroundColor: '#a67c52',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  linkButton: {
    alignItems: 'center',
    marginTop: 16,
  },
  linkText: {
    color: '#a67c52',
    fontSize: 14,
  },
  errorText: {
    color: '#ff6b6b',
    fontSize: 12,
    marginTop: 4,
  },
});