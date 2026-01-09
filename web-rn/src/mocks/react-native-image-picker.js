// Mock for react-native-image-picker on web
export const launchCamera = (options, callback) => {
  console.warn('Camera not available on web platform');
  if (callback) {
    callback({ didCancel: true });
  }
};

export const launchImageLibrary = (options, callback) => {
  console.warn('Image library not available on web platform');
  if (callback) {
    callback({ didCancel: true });
  }
};

// Mock types for TypeScript compatibility
export const MediaType = {
  photo: 'photo',
  video: 'video',
  mixed: 'mixed'
};

export default {
  launchCamera,
  launchImageLibrary,
  MediaType
};