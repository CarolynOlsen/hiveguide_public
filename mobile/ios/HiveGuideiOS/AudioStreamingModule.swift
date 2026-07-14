//
//  AudioStreamingModule.swift
//  HiveGuideiOS
//
//  Real-time audio streaming module using AVAudioEngine
//

import Foundation
import AVFoundation
import React
import os.log

@objc(AudioStreamingModule)
class AudioStreamingModule: RCTEventEmitter {

  // Enhanced logging for debugging
  private static let logger = OSLog(subsystem: "com.hiveguide.audio", category: "streaming")

  private var audioEngine: AVAudioEngine?
  private var inputNode: AVAudioInputNode?
  private var isStreaming = false
  private var audioSession: AVAudioSession?
  private var audioConverter: AVAudioConverter?

  // Logging helpers
  private func logDebug(_ message: String) {
    os_log(.debug, log: Self.logger, "%{public}@", message)
    print("[AudioDebug] \(message)")
  }

  private func logError(_ message: String, _ error: Error? = nil) {
    let errorDesc = error?.localizedDescription ?? "no error object"
    os_log(.error, log: Self.logger, "%{public}@ | Error: %{public}@", message, errorDesc)
    print("[AudioError] \(message) | Error: \(errorDesc)")
  }

  private func logInfo(_ message: String) {
    os_log(.info, log: Self.logger, "%{public}@", message)
    print("[AudioInfo] \(message)")
  }
  
  override init() {
    super.init()
    NSLog("🟢🟢🟢 AudioStreamingModule INITIALIZED - Module loaded successfully! 🟢🟢🟢")
    setupAudioSession()
  }
  
  deinit {
    NotificationCenter.default.removeObserver(self)
    cleanup()
  }
  
  private func setupAudioSession() {
    audioSession = AVAudioSession.sharedInstance()
    // Note: AVAudioSessionDelegate is deprecated in iOS, using notification center instead
    setupAudioSessionNotifications()
  }
  
  private func setupAudioSessionNotifications() {
    NotificationCenter.default.addObserver(
      self,
      selector: #selector(audioSessionInterruptionNotification(_:)),
      name: AVAudioSession.interruptionNotification,
      object: nil
    )
    
    NotificationCenter.default.addObserver(
      self,
      selector: #selector(audioSessionRouteChangeNotification(_:)),
      name: AVAudioSession.routeChangeNotification,
      object: nil
    )
  }
  
  private func cleanup() {
    stopAudioEngine()
    audioSession = nil
  }
  
  @objc
  override static func requiresMainQueueSetup() -> Bool {
    return false
  }
  
  override func supportedEvents() -> [String]! {
    return ["onAudioChunk", "onStreamingError", "onStreamingStarted", "onStreamingStopped", "onDiagnostic"]
  }
  
  @objc
  func startStreaming(_ sampleRate: NSNumber,
                     chunkDuration: NSNumber,
                     resolve: @escaping RCTPromiseResolveBlock,
                     reject: @escaping RCTPromiseRejectBlock) {

    NSLog("🔴🔴🔴 AudioStreamingModule.startStreaming() CALLED 🔴🔴🔴")
    logInfo("========== START STREAMING CALLED ==========")
    logDebug("Parameters - sampleRate: \(sampleRate), chunkDuration: \(chunkDuration)")

    DispatchQueue.global(qos: .userInitiated).async { [weak self] in
      guard let self = self else {
        self?.logError("Module deallocated during startStreaming")
        reject("ERROR", "Module deallocated", nil)
        return
      }

      // Check if running in simulator - AVAudioEngine doesn't work in simulator
      #if targetEnvironment(simulator)
      self.logInfo("Running in simulator - audio streaming not supported")
      reject("SIMULATOR_LIMITATION", "Audio streaming not supported in iOS Simulator. Please test on a physical device.", nil)
      return
      #else
      self.logInfo("Running on physical device - attempting audio streaming")
      #endif

      // Check if already streaming
      if self.isStreaming {
        self.logError("Cannot start - already streaming")
        reject("ERROR", "Already streaming", nil)
        return
      }

      self.logDebug("Streaming check passed, beginning audio session setup")
      
      do {
        // Configure audio session
        self.logDebug("Step 1: Getting audio session instance")
        guard let audioSession = self.audioSession else {
          self.logError("Audio session not initialized")
          reject("ERROR", "Audio session not initialized", nil)
          return
        }

        // Check microphone permission first
        self.logDebug("Step 2: Checking microphone permission - status: \(audioSession.recordPermission.rawValue)")
        guard audioSession.recordPermission == .granted else {
          self.logError("Microphone permission not granted - status: \(audioSession.recordPermission.rawValue)")
          reject("PERMISSION_DENIED", "Microphone permission not granted. Please enable microphone access in Settings.", nil)
          return
        }
        self.logInfo("✅ Microphone permission granted")

        // Deactivate any existing session first
        self.logDebug("Step 3: Deactivating existing audio session")
        try audioSession.setActive(false, options: .notifyOthersOnDeactivation)
        
        // Set proper audio session category for recording
        self.logDebug("Step 4: Setting audio session category to .playAndRecord")
        try audioSession.setCategory(.playAndRecord, mode: .measurement, options: [.allowBluetooth, .allowBluetoothA2DP, .defaultToSpeaker])
        self.logInfo("✅ Audio session category set")

        self.logDebug("Step 5: Activating audio session")
        try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        self.logInfo("✅ Audio session activated")

        // Give the audio session a moment to fully initialize
        self.logDebug("Step 6: Waiting 0.5s for audio session to stabilize")
        Thread.sleep(forTimeInterval: 0.5)

        // Clean up any existing audio engine
        self.stopAudioEngine()

        // Create audio engine
        self.logDebug("Step 7: Creating AVAudioEngine instance")
        self.audioEngine = AVAudioEngine()
        guard let audioEngine = self.audioEngine else {
          self.logError("Failed to create audio engine - instance is nil")
          reject("ERROR", "Failed to create audio engine", nil)
          return
        }
        self.logInfo("✅ Audio engine created")

        self.logDebug("Step 8: Getting input node from audio engine")
        self.inputNode = audioEngine.inputNode
        guard let inputNode = self.inputNode else {
          self.logError("Input node is nil - no audio input available")
          reject("ERROR", "No input node available", nil)
          return
        }
        self.logInfo("✅ Input node obtained")
        
        // Get the input node's native format
        self.logDebug("Step 9: Getting input node's native format")
        let inputFormat = inputNode.outputFormat(forBus: 0)
        self.logDebug("Input format - channels: \(inputFormat.channelCount), sampleRate: \(inputFormat.sampleRate), format: \(inputFormat)")
        
        // Additional safety check - ensure input node is properly initialized
        guard inputFormat.channelCount > 0 else {
          self.logError("Input node has no channels available")
          reject("ERROR", "Input node not properly initialized - no channels available", nil)
          return
        }
        self.logInfo("✅ Input node has \(inputFormat.channelCount) channels at \(inputFormat.sampleRate)Hz")

        // Calculate buffer size based on INPUT sample rate and chunk duration
        let chunkDurationSeconds = chunkDuration.doubleValue / 1000.0
        let bufferSize = AVAudioFrameCount(inputFormat.sampleRate * chunkDurationSeconds)
        self.logDebug("Step 10: Calculated buffer size: \(bufferSize) frames (\(chunkDurationSeconds)s chunks at \(inputFormat.sampleRate)Hz)")

        // Create output format for conversion (16kHz, mono, 16-bit PCM for Assembly AI)
        self.logDebug("Step 11: Creating output format for conversion (PCM Int16, \(sampleRate)Hz, mono)")
        let sampleRateValue = sampleRate.doubleValue
        let outputFormat = AVAudioFormat(
          commonFormat: .pcmFormatInt16,
          sampleRate: sampleRateValue,
          channels: 1,
          interleaved: true
        )

        guard let format = outputFormat else {
          self.logError("Failed to create output audio format")
          reject("ERROR", "Failed to create output audio format", nil)
          return
        }
        self.logInfo("✅ Output format created: \(format)")

        // Create format converter
        self.logDebug("Step 12: Creating audio converter from \(inputFormat.sampleRate)Hz to \(sampleRateValue)Hz")
        guard let converter = AVAudioConverter(from: inputFormat, to: format) else {
          self.logError("Failed to create audio format converter")
          reject("ERROR", "Failed to create audio format converter", nil)
          return
        }
        self.audioConverter = converter
        self.logInfo("✅ Audio converter created")

        var chunkIndex = 0

        // Install tap on input node using the INPUT format (not output format)
        self.logDebug("Step 13: Installing audio tap on input node using native format")
        self.logInfo("About to call inputNode.installTap() - buffer: \(bufferSize), format: \(inputFormat)")
        inputNode.installTap(onBus: 0, bufferSize: bufferSize, format: inputFormat) { [weak self] (buffer, time) in
            NSLog("🎤 AUDIO TAP FIRED! frameLength: \(buffer.frameLength)")
            guard let self = self, let converter = self.audioConverter else {
              NSLog("🔴 Audio tap: self or converter is nil")
              return
            }
            
            // Send diagnostic alert every 5th chunk
            if chunkIndex % 5 == 0 {
              self.sendEvent(withName: "onDiagnostic", body: [
                "step": "audio_tap",
                "message": "🎤 Audio tap fired! Chunk #\(chunkIndex)",
                "chunkIndex": chunkIndex
              ])
            }

          // Convert the buffer to the output format (16kHz mono Int16)
          let outputFrameCapacity = AVAudioFrameCount((Double(buffer.frameLength) * format.sampleRate) / inputFormat.sampleRate)
          guard let convertedBuffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: outputFrameCapacity) else {
            self.logError("Failed to create converted buffer")
            return
          }

          var error: NSError?
          let inputBlock: AVAudioConverterInputBlock = { inNumPackets, outStatus in
            outStatus.pointee = .haveData
            return buffer
          }

          converter.convert(to: convertedBuffer, error: &error, withInputFrom: inputBlock)

          if let error = error {
            self.logError("Audio conversion failed", error)
            return
          }

          // Convert audio buffer to Data
          guard let channelData = convertedBuffer.int16ChannelData else {
            self.logError("No int16 channel data available after conversion")
            return
          }
          let channelDataValue = channelData.pointee
          let channelDataValueArray = stride(from: 0, to: Int(convertedBuffer.frameLength), by: convertedBuffer.stride).map { channelDataValue[$0] }
          let data = Data(bytes: channelDataValueArray, count: channelDataValueArray.count * MemoryLayout<Int16>.size)

          // Convert to base64 for transmission
          let base64String = data.base64EncodedString()

          // Send audio chunk event to React Native
          NSLog("📡 Sending onAudioChunk event #\(chunkIndex) to React Native")
          self.sendEvent(withName: "onAudioChunk", body: [
            "data": base64String,
            "timestamp": time.sampleTime,
            "chunkIndex": chunkIndex
          ])
          
          // Send diagnostic alert every 5th chunk after sending
          if chunkIndex % 5 == 0 {
            self.sendEvent(withName: "onDiagnostic", body: [
              "step": "chunk_sent_to_rn",
              "message": "📡 Sent chunk #\(chunkIndex) to React Native",
              "chunkIndex": chunkIndex
            ])
          }

          chunkIndex += 1
        }
        self.logInfo("✅ Audio tap installed successfully!")

        // Start the audio engine
        self.logDebug("Step 14: Starting audio engine")
        try audioEngine.start()
        self.isStreaming = true
        NSLog("✅✅✅ Audio engine STARTED - isStreaming = true ✅✅✅")
        self.logInfo("✅ Audio engine started - streaming is now active!")

        // Send started event
        NSLog("📤 Sending onStreamingStarted event to React Native")
        self.logDebug("Step 15: Sending onStreamingStarted event to React Native")
        self.sendEvent(withName: "onStreamingStarted", body: [:])

        self.logInfo("========== STREAMING STARTED SUCCESSFULLY ==========")
        resolve(true)

      } catch {
        self.logError("FAILED to start audio streaming - outer catch block", error)
        self.logError("Error domain: \((error as NSError).domain), code: \((error as NSError).code)")
        reject("ERROR", "Failed to start audio streaming: \(error.localizedDescription)", error)
      }
    }
  }
  
  @objc
  func stopStreaming(_ resolve: @escaping RCTPromiseResolveBlock,
                     reject: @escaping RCTPromiseRejectBlock) {

    NSLog("🛑🛑🛑 AudioStreamingModule.stopStreaming() CALLED 🛑🛑🛑")
    NSLog("🛑 Stack trace: %@", Thread.callStackSymbols.joined(separator: "\n"))
    logInfo("========== STOP STREAMING CALLED ==========")

    DispatchQueue.global(qos: .userInitiated).async { [weak self] in
      guard let self = self else {
        self?.logError("Module deallocated during stopStreaming")
        reject("ERROR", "Module deallocated", nil)
        return
      }

      guard self.isStreaming else {
        self.logError("Cannot stop - not currently streaming")
        reject("ERROR", "Not currently streaming", nil)
        return
      }

      // Use the centralized cleanup method
      self.stopAudioEngine()

      // Send stopped event
      self.logDebug("Sending onStreamingStopped event to React Native")
      self.sendEvent(withName: "onStreamingStopped", body: [:])

      self.logInfo("========== STREAMING STOPPED SUCCESSFULLY ==========")
      resolve(true)
    }
  }
  
  @objc
  func isCurrentlyStreaming(_ resolve: @escaping RCTPromiseResolveBlock,
                           reject: @escaping RCTPromiseRejectBlock) {
    resolve(self.isStreaming)
  }
  
  @objc
  func requestMicrophonePermission(_ resolve: @escaping RCTPromiseResolveBlock,
                                   reject: @escaping RCTPromiseRejectBlock) {
    guard let audioSession = self.audioSession else {
      reject("ERROR", "Audio session not initialized", nil)
      return
    }
    
    let currentStatus = audioSession.recordPermission
    
    switch currentStatus {
    case .granted:
      logInfo("Microphone permission already granted")
      resolve(true)
    case .denied:
      logError("Microphone permission denied - user must enable in Settings")
      reject("PERMISSION_DENIED", "Microphone permission denied. Please enable in Settings > Hive Guide.", nil)
    case .undetermined:
      logInfo("Microphone permission undetermined - requesting permission")
      audioSession.requestRecordPermission { granted in
        DispatchQueue.main.async {
          if granted {
            self.logInfo("✅ Microphone permission granted by user")
            resolve(true)
          } else {
            self.logError("❌ Microphone permission denied by user")
            reject("PERMISSION_DENIED", "Microphone permission denied. Please enable in Settings > Hive Guide.", nil)
          }
        }
      }
    @unknown default:
      logError("Unknown microphone permission status")
      reject("ERROR", "Unknown permission status", nil)
    }
  }
  
  // MARK: - Audio Session Notifications
  
  @objc private func audioSessionInterruptionNotification(_ notification: Notification) {
    NSLog("⚠️ audioSessionInterruptionNotification received: %@", notification.debugDescription)
    guard let userInfo = notification.userInfo,
          let typeValue = userInfo[AVAudioSessionInterruptionTypeKey] as? UInt,
          let type = AVAudioSession.InterruptionType(rawValue: typeValue) else {
      NSLog("⚠️ Could not parse interruption notification")
      return
    }

    switch type {
    case .began:
      NSLog("⚠️⚠️⚠️ Audio session INTERRUPTED - stopping audio engine")
      logInfo("Audio session interrupted")
      stopAudioEngine()
    case .ended:
      logInfo("Audio session interruption ended")
      if let optionsValue = userInfo[AVAudioSessionInterruptionOptionKey] as? UInt {
        let options = AVAudioSession.InterruptionOptions(rawValue: optionsValue)
        if options.contains(.shouldResume) {
          // Optionally restart audio if needed
          logInfo("Should resume audio after interruption")
        }
      }
    @unknown default:
      break
    }
  }
  
  @objc private func audioSessionRouteChangeNotification(_ notification: Notification) {
    logInfo("Audio route changed: \(notification)")
    // Handle route changes if needed
  }
  
  // MARK: - Private Helper Methods
  
  private func stopAudioEngine() {
    guard isStreaming else { return }

    NSLog("🔴 stopAudioEngine() called - Stack trace:")
    NSLog("%@", Thread.callStackSymbols.joined(separator: "\n"))
    logDebug("Stopping audio engine...")
    
    // Remove tap first
    if let inputNode = inputNode {
      inputNode.removeTap(onBus: 0)
    }
    
    // Stop engine
    audioEngine?.stop()
    audioEngine = nil
    inputNode = nil
    audioConverter = nil
    isStreaming = false
    
    // Deactivate session
    do {
      try audioSession?.setActive(false, options: .notifyOthersOnDeactivation)
      logInfo("✅ Audio session deactivated")
    } catch {
      logError("Failed to deactivate audio session", error)
    }
  }
}
