/**
 * Web-specific ImagePicker component
 * Uses HTML5 file input for image selection
 */

import { useRef } from 'react';

export interface ImagePickerOptions {
  mediaType?: 'photo' | 'video' | 'mixed';
  maxWidth?: number;
  maxHeight?: number;
  quality?: number;
  includeBase64?: boolean;
  selectionLimit?: number;
}

export interface ImagePickerAsset {
  uri: string;
  width?: number;
  height?: number;
  fileSize?: number;
  type?: string;
  fileName?: string;
  base64?: string;
}

export interface ImagePickerResponse {
  didCancel?: boolean;
  errorCode?: string;
  errorMessage?: string;
  assets?: ImagePickerAsset[];
}

export type Callback = (response: ImagePickerResponse) => void;

/**
 * Launch camera to take a photo (web: uses file input with capture)
 */
export function launchCamera(
  options: ImagePickerOptions,
  callback?: Callback
): Promise<ImagePickerResponse> {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.capture = 'environment' as any;

    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      if (!file) {
        const response: ImagePickerResponse = { didCancel: true };
        callback?.(response);
        resolve(response);
        return;
      }

      const uri = URL.createObjectURL(file);
      const asset: ImagePickerAsset = {
        uri,
        type: file.type,
        fileName: file.name,
        fileSize: file.size,
      };

      if (options.includeBase64) {
        const reader = new FileReader();
        reader.onloadend = () => {
          asset.base64 = reader.result as string;
          const response: ImagePickerResponse = { assets: [asset] };
          callback?.(response);
          resolve(response);
        };
        reader.readAsDataURL(file);
      } else {
        const response: ImagePickerResponse = { assets: [asset] };
        callback?.(response);
        resolve(response);
      }
    };

    input.click();
  });
}

/**
 * Launch image library to select a photo
 */
export function launchImageLibrary(
  options: ImagePickerOptions,
  callback?: Callback
): Promise<ImagePickerResponse> {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = options.mediaType === 'video' ? 'video/*' : 'image/*';
    input.multiple = (options.selectionLimit || 1) > 1;

    input.onchange = async (e: any) => {
      const files = Array.from(e.target.files || []) as File[];
      
      if (files.length === 0) {
        const response: ImagePickerResponse = { didCancel: true };
        callback?.(response);
        resolve(response);
        return;
      }

      const assets: ImagePickerAsset[] = [];

      for (const file of files) {
        const uri = URL.createObjectURL(file);
        const asset: ImagePickerAsset = {
          uri,
          type: file.type,
          fileName: file.name,
          fileSize: file.size,
        };

        if (options.includeBase64) {
          const base64 = await new Promise<string>((res) => {
            const reader = new FileReader();
            reader.onloadend = () => res(reader.result as string);
            reader.readAsDataURL(file);
          });
          asset.base64 = base64;
        }

        assets.push(asset);
      }

      const response: ImagePickerResponse = { assets };
      callback?.(response);
      resolve(response);
    };

    input.click();
  });
}

/**
 * Hook for image picker functionality
 */
export function useImagePicker() {
  return {
    launchCamera,
    launchImageLibrary,
  };
}
