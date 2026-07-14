//
//  AudioStreamingModule.m
//  HiveGuideiOS
//
//  Bridge between Swift and React Native
//

#import <React/RCTBridgeModule.h>
#import <React/RCTEventEmitter.h>

@interface RCT_EXTERN_MODULE(AudioStreamingModule, RCTEventEmitter)

RCT_EXTERN_METHOD(startStreaming:(nonnull NSNumber *)sampleRate
                  chunkDuration:(nonnull NSNumber *)chunkDuration
                  resolve:(RCTPromiseResolveBlock)resolve
                  reject:(RCTPromiseRejectBlock)reject)

RCT_EXTERN_METHOD(stopStreaming:(RCTPromiseResolveBlock)resolve
                  reject:(RCTPromiseRejectBlock)reject)

RCT_EXTERN_METHOD(isCurrentlyStreaming:(RCTPromiseResolveBlock)resolve
                  reject:(RCTPromiseRejectBlock)reject)

RCT_EXTERN_METHOD(requestMicrophonePermission:(RCTPromiseResolveBlock)resolve
                  reject:(RCTPromiseRejectBlock)reject)

@end
