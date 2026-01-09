#!/bin/bash

# Audio Testing Script for iOS
# This script helps test audio functionality

echo "🎵 HiveScribe iOS Audio Testing Script"
echo "======================================"

# Check if we're in the right directory
if [ ! -f "Podfile" ]; then
    echo "❌ Error: Please run this script from the mobile/ios directory"
    exit 1
fi

echo "📱 Checking iOS Simulator vs Device..."
if xcrun simctl list devices | grep -q "Booted"; then
    echo "⚠️  iOS Simulator detected - audio streaming will not work"
    echo "   Please test on a physical device for audio functionality"
else
    echo "✅ No simulator detected - assuming physical device"
fi

echo ""
echo "🔧 Checking Pod installation..."
if [ -d "Pods" ]; then
    echo "✅ Pods directory exists"
else
    echo "❌ Pods directory missing - run 'pod install'"
    exit 1
fi

echo ""
echo "📋 Checking Info.plist for audio permissions..."
if grep -q "NSMicrophoneUsageDescription" HiveScribeiOS/Info.plist; then
    echo "✅ Microphone permission description found"
else
    echo "❌ Missing NSMicrophoneUsageDescription in Info.plist"
fi

if grep -q "UIBackgroundModes" HiveScribeiOS/Info.plist; then
    echo "✅ Background audio mode found"
else
    echo "❌ Missing UIBackgroundModes in Info.plist"
fi

echo ""
echo "🔍 Checking AudioStreamingModule files..."
if [ -f "HiveScribeiOS/AudioStreamingModule.swift" ]; then
    echo "✅ AudioStreamingModule.swift exists"
else
    echo "❌ AudioStreamingModule.swift missing"
fi

if [ -f "HiveScribeiOS/AudioStreamingModule.m" ]; then
    echo "✅ AudioStreamingModule.m exists"
else
    echo "❌ AudioStreamingModule.m missing"
fi

echo ""
echo "🏗️  Building project..."
# Try to build for physical device if available, otherwise use simulator
if xcrun simctl list devices | grep -q "Carolyn's Phone of Doom"; then
    echo "📱 Building for physical device: Carolyn's Phone of Doom"
    xcodebuild -workspace HiveScribeiOS.xcworkspace -scheme HiveScribeiOS -configuration Debug -destination 'platform=iOS,name=Carolyn'\''s Phone of Doom' build
else
    echo "📱 Building for simulator: iPhone 16"
    xcodebuild -workspace HiveScribeiOS.xcworkspace -scheme HiveScribeiOS -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 16' build
fi

if [ $? -eq 0 ]; then
    echo "✅ Build successful"
else
    echo "❌ Build failed - check Xcode for errors"
    exit 1
fi

echo ""
echo "🎯 Audio testing complete!"
echo "   If testing on device, check Console.app for audio logs"
echo "   Look for '[AudioDebug]', '[AudioInfo]', and '[AudioError]' messages"