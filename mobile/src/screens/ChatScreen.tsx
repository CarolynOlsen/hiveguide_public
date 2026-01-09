import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  Keyboard,
  Linking,
} from 'react-native';
import { useMutation } from '@tanstack/react-query';
import { apiService } from '../services/api';
import Markdown from 'react-native-markdown-display';

interface Citation {
  id: number;
  page?: number;
  page_range?: string;
  title: string;
  organization?: string;
  year?: number;
  url?: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
}

const MessageBubble = ({ message }: { message: ChatMessage }) => {
  const isUser = message.role === 'user';
  
  const handleCitationPress = (url: string | undefined) => {
    if (url) {
      Linking.openURL(url);
    }
  };
  
  return (
    <View style={[
      styles.messageBubble,
      isUser ? styles.userBubble : styles.assistantBubble
    ]}>
      {isUser ? (
        <Text style={[
          styles.messageText,
          styles.userText
        ]}>
          {message.content}
        </Text>
      ) : (
        <Markdown
          style={{
            body: styles.markdownBody,
            text: styles.messageText,
            paragraph: styles.markdownParagraph,
            strong: styles.markdownStrong,
            em: styles.markdownEm,
            bullet_list: styles.markdownList,
            ordered_list: styles.markdownList,
          }}
        >
          {message.content}
        </Markdown>
      )}
      
      {message.citations && message.citations.length > 0 && (
        <View style={styles.citationsContainer}>
          <Text style={styles.citationsHeader}>More Reading:</Text>
          {message.citations.map((citation, index) => (
            <View key={index} style={styles.citationItem}>
              {citation.url ? (
                <TouchableOpacity onPress={() => handleCitationPress(citation.url)}>
                  <Text style={styles.citationLink}>[{citation.id}]</Text>
                </TouchableOpacity>
              ) : (
                <Text style={styles.citationNumber}>[{citation.id}]</Text>
              )}
              <Text style={styles.citationDetails}>
                {citation.page_range ? `p. ${citation.page_range}, ` : (citation.page ? `p. ${citation.page}, ` : '')}
                {citation.title}
                {(citation.organization || citation.year) ? ` (${[citation.organization, citation.year].filter(Boolean).join(', ')})` : ''}
              </Text>
            </View>
          ))}
        </View>
      )}
      
      <Text style={styles.timestamp}>
        {message.timestamp.toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit' 
        })}
      </Text>
    </View>
  );
};

export default function ChatScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hi! I'm your beekeeping assistant. Ask me anything about your hives, bee behavior, seasonal care tips, or any beekeeping questions you have!",
      timestamp: new Date(),
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [hasUserSentMessage, setHasUserSentMessage] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  const sendMessageMutation = useMutation({
    mutationFn: async (message: string) => {
      const response = await apiService.sendChatMessage(message);
      return response;
    },
    onSuccess: (data) => {
      // Transform sources into citation format (same as web app)
      const citations = (data.sources || []).map((source: any, index: number) => {
        let finalUrl = source.source_url;
        if (finalUrl && source.page_number) {
          finalUrl = `${finalUrl}#page=${source.page_number}`;
        }
        
        return {
          id: index + 1,
          page: source.page_number,
          page_range: source.page_range,
          title: source.document_title || 'Unknown Document',
          organization: source.organization,
          year: source.publication_year,
          url: finalUrl
        };
      });
      
      // Add assistant response with citations
      const assistantMessage: ChatMessage = {
        id: Date.now().toString() + '_assistant',
        role: 'assistant',
        content: data.answer,
        timestamp: new Date(),
        citations: citations.length > 0 ? citations : undefined,
      };
      setMessages(prev => [...prev, assistantMessage]);
    },
    onError: (error) => {
      Alert.alert('Error', 'Failed to send message. Please try again.');
      console.error('Chat error:', error);
    },
  });

  const handleSendMessage = () => {
    if (!inputText.trim()) return;
    
    // Mark that user has sent at least one message
    setHasUserSentMessage(true);
    
    // Add user message immediately
    const userMessage: ChatMessage = {
      id: Date.now().toString() + '_user',
      role: 'user',
      content: inputText.trim(),
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    
    // Dismiss keyboard
    Keyboard.dismiss();
    
    // Send to API
    sendMessageMutation.mutate(inputText.trim());
  };

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (flatListRef.current) {
      flatListRef.current.scrollToEnd({ animated: true });
    }
  }, [messages]);

  const quickActions = [
    "How are my hives doing?",
    "What should I check in my next inspection?",
    "Show me recent action items",
    "What's the weather like for beekeeping today?",
  ];

  const handleQuickAction = (action: string) => {
    setInputText(action);
    // Automatically send the message when quick action is selected
    setTimeout(() => {
      if (action.trim()) {
        setHasUserSentMessage(true);
        const userMessage: ChatMessage = {
          id: Date.now().toString() + '_user',
          role: 'user',
          content: action.trim(),
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, userMessage]);
        setInputText('');
        Keyboard.dismiss();
        sendMessageMutation.mutate(action.trim());
      }
    }, 100);
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {/* Messages List */}
      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <MessageBubble message={item} />}
        contentContainerStyle={styles.messagesContainer}
        showsVerticalScrollIndicator={false}
      />

      {/* Loading indicator for AI response */}
      {sendMessageMutation.isPending && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color="#a67c52" />
          <Text style={styles.loadingText}>AI is thinking...</Text>
        </View>
      )}

      {/* Quick Actions */}
      {!hasUserSentMessage && (
        <View style={styles.quickActions}>
          <Text style={styles.quickActionsTitle}>Quick Questions:</Text>
          <View style={styles.quickActionsGrid}>
            {quickActions.map((action, index) => (
              <TouchableOpacity
                key={index}
                style={styles.quickActionButton}
                onPress={() => handleQuickAction(action)}
              >
                <Text style={styles.quickActionText}>{action}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

      {/* Input Area */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Ask me about your hives..."
          placeholderTextColor="#999"
          multiline
          maxLength={500}
        />
        <TouchableOpacity
          style={[
            styles.sendButton,
            (!inputText.trim() || sendMessageMutation.isPending) && styles.sendButtonDisabled
          ]}
          onPress={handleSendMessage}
          disabled={!inputText.trim() || sendMessageMutation.isPending}
        >
          <Text style={styles.sendButtonText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff8f0',
  },
  messagesContainer: {
    padding: 16,
    paddingBottom: 8,
  },
  messageBubble: {
    maxWidth: '80%',
    padding: 12,
    borderRadius: 16,
    marginVertical: 4,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#a67c52',
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: 'white',
    borderBottomLeftRadius: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  messageText: {
    fontSize: 16,
    lineHeight: 22,
  },
  userText: {
    color: 'white',
  },
  assistantText: {
    color: '#333',
  },
  timestamp: {
    fontSize: 11,
    opacity: 0.7,
    marginTop: 4,
    alignSelf: 'flex-end',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
  },
  loadingText: {
    marginLeft: 8,
    fontSize: 14,
    color: '#6d4c1b',
    fontStyle: 'italic',
  },
  quickActions: {
    padding: 16,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#eee',
    backgroundColor: 'white',
  },
  quickActionsTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#a67c52',
    marginBottom: 8,
  },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  quickActionButton: {
    backgroundColor: '#fbeee6',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#ddd',
  },
  quickActionText: {
    fontSize: 12,
    color: '#6d4c1b',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 16,
    backgroundColor: 'white',
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  textInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 12,
    maxHeight: 100,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  sendButton: {
    backgroundColor: '#a67c52',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 20,
    marginLeft: 8,
  },
  sendButtonDisabled: {
    backgroundColor: '#ccc',
  },
  sendButtonText: {
    color: 'white',
    fontWeight: 'bold',
    fontSize: 16,
  },
  // Markdown styles
  markdownBody: {
    color: '#333',
  },
  markdownParagraph: {
    marginTop: 0,
    marginBottom: 8,
  },
  markdownStrong: {
    fontWeight: 'bold',
  },
  markdownEm: {
    fontStyle: 'italic',
  },
  markdownList: {
    marginBottom: 8,
  },
  // Citation styles
  citationsContainer: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
  citationsHeader: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#6d4c1b',
    marginBottom: 8,
  },
  citationItem: {
    flexDirection: 'row',
    marginBottom: 6,
    flexWrap: 'wrap',
  },
  citationLink: {
    color: '#a67c52',
    fontWeight: 'bold',
    fontSize: 14,
    marginRight: 6,
    textDecorationLine: 'underline',
  },
  citationNumber: {
    color: '#6d4c1b',
    fontWeight: 'bold',
    fontSize: 14,
    marginRight: 6,
  },
  citationDetails: {
    flex: 1,
    fontSize: 12,
    color: '#555',
    lineHeight: 18,
  },
});