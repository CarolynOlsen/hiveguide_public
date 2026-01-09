#!/bin/bash

# Audio Module Pre-flight Checks
# Validates audio configuration before building and deploying

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Audio Module Pre-flight Checks${NC}"
echo "=================================="
echo ""

CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

# Helper functions
pass() {
    echo -e "${GREEN}✅ $1${NC}"
    ((CHECKS_PASSED++))
}

fail() {
    echo -e "${RED}❌ $1${NC}"
    ((CHECKS_FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Navigate to mobile directory if not already there
if [ ! -f "package.json" ]; then
    if [ -f "../package.json" ] && [ -d "../ios" ]; then
        cd ..
    elif [ -f "../../package.json" ] && [ -d "../../ios" ]; then
        cd ../..
    else
        fail "Cannot find mobile directory with package.json"
        exit 1
    fi
fi

echo -e "${BLUE}Check 1: AudioStreamingModule.swift exists${NC}"
if [ -f "ios/HiveScribeiOS/AudioStreamingModule.swift" ]; then
    pass "AudioStreamingModule.swift found"
else
    fail "AudioStreamingModule.swift not found at ios/HiveScribeiOS/"
fi

echo ""
echo -e "${BLUE}Check 2: Microphone permission in Info.plist${NC}"
if grep -q "NSMicrophoneUsageDescription" ios/HiveScribeiOS/Info.plist 2>/dev/null; then
    PERM_TEXT=$(grep -A 1 "NSMicrophoneUsageDescription" ios/HiveScribeiOS/Info.plist | tail -1 | sed 's/<[^>]*>//g' | xargs)
    pass "Microphone permission configured"
    info "Permission text: \"$PERM_TEXT\""
else
    fail "Missing NSMicrophoneUsageDescription in Info.plist"
fi

echo ""
echo -e "${BLUE}Check 3: Audio Transport Security settings${NC}"
if grep -q "NSAppTransportSecurity" ios/HiveScribeiOS/Info.plist 2>/dev/null; then
    pass "NSAppTransportSecurity configured"

    # Check for AssemblyAI domains
    if grep -q "assemblyai.com" ios/HiveScribeiOS/Info.plist; then
        pass "AssemblyAI domain exceptions configured"
    else
        warn "AssemblyAI domain exceptions not found in Info.plist"
    fi
else
    fail "NSAppTransportSecurity not configured"
fi

echo ""
echo -e "${BLUE}Check 4: React Native bridge module registration${NC}"
# Check if the module has the required @objc decorator
if grep -q "@objc(AudioStreamingModule)" ios/HiveScribeiOS/AudioStreamingModule.swift 2>/dev/null; then
    pass "AudioStreamingModule has @objc decorator"
else
    fail "AudioStreamingModule missing @objc decorator"
fi

# Check for requiresMainQueueSetup
if grep -q "requiresMainQueueSetup" ios/HiveScribeiOS/AudioStreamingModule.swift 2>/dev/null; then
    pass "requiresMainQueueSetup implemented"
else
    warn "requiresMainQueueSetup not found (may cause warnings)"
fi

# Check for supportedEvents
if grep -q "supportedEvents" ios/HiveScribeiOS/AudioStreamingModule.swift 2>/dev/null; then
    pass "supportedEvents implemented"
else
    fail "supportedEvents not found (required for event emission)"
fi

echo ""
echo -e "${BLUE}Check 5: AVFoundation framework import${NC}"
if grep -q "import AVFoundation" ios/HiveScribeiOS/AudioStreamingModule.swift 2>/dev/null; then
    pass "AVFoundation imported"
else
    fail "AVFoundation not imported"
fi

echo ""
echo -e "${BLUE}Check 6: React Native import${NC}"
if grep -q "import React" ios/HiveScribeiOS/AudioStreamingModule.swift 2>/dev/null; then
    pass "React Native framework imported"
else
    fail "React Native framework not imported"
fi

echo ""
echo -e "${BLUE}Check 7: TypeScript module definition${NC}"
if [ -f "src/services/AudioStreamingModule.ts" ] || [ -f "src/services/AudioStreamingModule.tsx" ]; then
    pass "AudioStreamingModule TypeScript definition found"
else
    warn "AudioStreamingModule TypeScript definition not found in src/services/"
fi

echo ""
echo -e "${BLUE}Check 8: TypeScript compilation${NC}"
if command -v npx &> /dev/null; then
    # Only check files related to audio/transcription
    if npx tsc --noEmit --skipLibCheck 2>&1 | grep -iE "(audio|transcription)" > /tmp/audio_tsc_errors.txt; then
        ERROR_COUNT=$(wc -l < /tmp/audio_tsc_errors.txt)
        fail "TypeScript errors found in audio/transcription files ($ERROR_COUNT issues)"
        echo -e "${YELLOW}First few errors:${NC}"
        head -5 /tmp/audio_tsc_errors.txt
    else
        pass "No TypeScript errors in audio/transcription files"
    fi
    rm -f /tmp/audio_tsc_errors.txt
else
    warn "TypeScript compiler not available (npx not found)"
fi

echo ""
echo -e "${BLUE}Check 9: CocoaPods integrity${NC}"
if [ -f "ios/Podfile.lock" ]; then
    pass "Podfile.lock exists"

    if [ -d "ios/Pods" ]; then
        pass "Pods directory exists"
    else
        fail "Pods directory missing - run 'cd ios && pod install'"
    fi
else
    fail "Podfile.lock missing - run 'cd ios && pod install'"
fi

echo ""
echo -e "${BLUE}Check 10: Metro bundler port${NC}"
if lsof -i:8081 > /dev/null 2>&1; then
    METRO_PID=$(lsof -ti:8081 | head -1)
    pass "Metro bundler running on port 8081 (PID: $METRO_PID)"
else
    warn "Metro bundler not running on port 8081"
    info "Start with: cd mobile && npx react-native start"
fi

echo ""
echo -e "${BLUE}Check 11: Enhanced logging configured${NC}"
if grep -q "os.log" ios/HiveScribeiOS/AudioStreamingModule.swift 2>/dev/null; then
    pass "Enhanced logging (os.log) configured"

    if grep -q "com.hiveguide.audio" ios/HiveScribeiOS/AudioStreamingModule.swift 2>/dev/null; then
        pass "Audio subsystem logger configured"
    else
        warn "Audio subsystem logger not found"
    fi
else
    warn "Enhanced logging not configured - harder to debug crashes"
fi

echo ""
echo -e "${BLUE}Check 12: Device connection${NC}"
DEVICE_ID="00008140-000E49991E63001C"
if xcrun xctrace list devices 2>/dev/null | grep -q "$DEVICE_ID"; then
    DEVICE_NAME=$(xcrun xctrace list devices 2>&1 | grep "$DEVICE_ID" | sed 's/ (.*//')
    pass "Target device connected: $DEVICE_NAME"
else
    warn "Target device (Carolyn's Phone of Doom) not connected"
    info "Connect via USB to deploy to physical device"
fi

# Summary
echo ""
echo "=================================="
echo -e "${BLUE}Pre-flight Check Summary${NC}"
echo "=================================="
echo -e "${GREEN}Passed:  $CHECKS_PASSED${NC}"
echo -e "${RED}Failed:  $CHECKS_FAILED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo ""

if [ $CHECKS_FAILED -gt 0 ]; then
    echo -e "${RED}❌ Pre-flight checks FAILED${NC}"
    echo -e "${YELLOW}Please fix the failed checks before building${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Pre-flight checks PASSED${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠️  There are $WARNINGS warnings - review above${NC}"
    fi
    exit 0
fi
