export const theme = {
  colors: {
    primary: '#a67c52',
    primaryLight: '#c89968',
    primaryDark: '#8a5e3c',
    background: '#fff8f0',
    surface: '#ffffff',
    textPrimary: '#333333',
    textSecondary: '#666666',
    textTertiary: '#888888',
    textOnPrimary: '#ffffff',
    accent: '#6d4c1b',
    error: '#ff6b6b',
    success: '#51cf66',
    warning: '#ffd43b',
    urgentRed: '#ff6b6b',
    attentionYellow: '#ffd43b',
    goodGreen: '#51cf66',
    border: '#e0e0e0',
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },
  borderRadius: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
  },
  typography: {
    sizes: {
      xs: 10,
      sm: 12,
      md: 14,
      lg: 16,
      xl: 18,
      xxl: 24,
      xxxl: 32,
    },
    weights: {
      regular: '400' as const,
      medium: '500' as const,
      semibold: '600' as const,
      bold: '700' as const,
    },
  },
  shadows: {
    card: {
      shadowColor: '#a67c52',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 4,
      elevation: 3,
    },
  },
};

export type Theme = typeof theme;
