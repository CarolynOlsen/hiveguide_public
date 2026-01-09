// Mock for react-native-screens on web
import React from 'react';

export const Screen = ({ children, ...props }) => 
  React.createElement('div', props, children);

export const ScreenContainer = ({ children, ...props }) => 
  React.createElement('div', props, children);

export const ScreenStack = ({ children, ...props }) => 
  React.createElement('div', props, children);

export const NativeScreen = Screen;
export const NativeScreenContainer = ScreenContainer;
export const NativeScreenStack = ScreenStack;

export const enableScreens = () => {
  console.log('react-native-screens: enableScreens() called (web mock)');
};

export default {
  Screen,
  ScreenContainer,
  ScreenStack,
  NativeScreen,
  NativeScreenContainer,
  NativeScreenStack,
  enableScreens,
};