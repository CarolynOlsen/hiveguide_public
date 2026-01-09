/**
 * Web-specific DatePicker component
 * Uses HTML5 date input for cross-platform compatibility
 */

import React from 'react';
import { View, Text, StyleSheet, TextInput } from 'react-native';

export interface DatePickerProps {
  value: Date;
  onChange: (event: any, date?: Date) => void;
  mode?: 'date' | 'time' | 'datetime';
  display?: 'default' | 'spinner' | 'calendar' | 'clock';
  maximumDate?: Date;
  minimumDate?: Date;
}

export const DateTimePicker: React.FC<DatePickerProps> = ({
  value,
  onChange,
  mode = 'date',
  maximumDate,
  minimumDate,
}) => {
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const dateValue = event.target.value;
    if (dateValue) {
      const newDate = new Date(dateValue);
      onChange({ type: 'set', nativeEvent: {} } as any, newDate);
    }
  };

  const formatDateForInput = (date: Date): string => {
    if (mode === 'time') {
      return date.toTimeString().slice(0, 5);
    }
    return date.toISOString().split('T')[0];
  };

  const inputType = mode === 'time' ? 'time' : 'date';

  return (
    <View style={styles.container}>
      <input
        type={inputType}
        value={formatDateForInput(value)}
        onChange={handleChange}
        max={maximumDate ? formatDateForInput(maximumDate) : undefined}
        min={minimumDate ? formatDateForInput(minimumDate) : undefined}
        style={{
          padding: 12,
          fontSize: 16,
          borderWidth: 1,
          borderColor: '#e0e0e0',
          borderRadius: 8,
          backgroundColor: '#ffffff',
          width: '100%',
        }}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
});

export default DateTimePicker;
