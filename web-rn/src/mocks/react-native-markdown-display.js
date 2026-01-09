// Mock for react-native-markdown-display on web
import React from 'react';
import { Text, View } from 'react-native';

// Simple markdown renderer for web that doesn't use require()
const Markdown = ({ children, style }) => {
  // Simple text processing for basic markdown
  const processText = (text) => {
    if (!text) return text;
    
    // Convert **bold** to styled text
    const boldParts = text.split(/\*\*(.*?)\*\*/g);
    if (boldParts.length > 1) {
      return boldParts.map((part, index) => {
        if (index % 2 === 1) {
          return (
            <Text key={index} style={{ fontWeight: 'bold' }}>
              {part}
            </Text>
          );
        }
        return part;
      });
    }
    
    return text;
  };

  return (
    <Text style={style?.text}>
      {processText(children)}
    </Text>
  );
};

export default Markdown;