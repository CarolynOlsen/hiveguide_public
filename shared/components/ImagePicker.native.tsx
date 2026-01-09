/**
 * Native ImagePicker component
 * Re-exports the native ImagePicker from react-native-image-picker
 */

export {
  launchCamera,
  launchImageLibrary,
  type ImagePickerOptions,
  type ImagePickerResponse,
  type ImagePickerAsset,
  type Callback,
} from 'react-native-image-picker';

export function useImagePicker() {
  const { launchCamera, launchImageLibrary } = require('react-native-image-picker');
  return {
    launchCamera,
    launchImageLibrary,
  };
}
