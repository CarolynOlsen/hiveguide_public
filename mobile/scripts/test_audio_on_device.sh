#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📱 iOS Audio Device Testing Script${NC}"
echo "=================================="

# Create output directory
OUTPUT_DIR="$HOME/Desktop/hiveguide_test_results"
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEST_DIR="$OUTPUT_DIR/$TIMESTAMP"
mkdir -p "$TEST_DIR"

echo -e "${BLUE}📁 Test results will be saved to: $TEST_DIR${NC}\n"

# Use hardcoded UDID for Carolyn's Phone of Doom (same as rebuild-ios.sh)
DEVICE_ID="00008140-000E49991E63001C"

echo -e "${BLUE}🔍 Looking for device: $DEVICE_ID (Carolyn's Phone of Doom)${NC}"

# Check if the device is connected
if ! xcrun xctrace list devices 2>/dev/null | grep -q "$DEVICE_ID"; then
    echo -e "${RED}❌ Device not connected. Please connect your iPhone via USB.${NC}"
    echo "Available devices:"
    xcrun xctrace list devices 2>&1
    exit 1
fi

DEVICE_NAME=$(xcrun xctrace list devices 2>&1 | grep "$DEVICE_ID" | sed 's/ (.*//')
echo -e "${GREEN}✅ Found device: $DEVICE_NAME${NC}"
echo -e "   Device ID: $DEVICE_ID\n"

# Check if device is paired
echo -e "${BLUE}🔒 Checking device pairing...${NC}"
if xcrun devicectl list devices 2>&1 | grep -q "$DEVICE_ID"; then
    echo -e "${GREEN}✅ Device is paired${NC}\n"
else
    echo -e "${YELLOW}⚠️  Device may not be fully paired. Please unlock your device and trust this computer.${NC}\n"
fi

# Build the app
echo -e "${BLUE}🔨 Building app...${NC}"
cd "$(dirname "$0")/../ios"

xcodebuild -workspace HiveScribeiOS.xcworkspace \
  -scheme HiveScribeiOS \
  -configuration Debug \
  -derivedDataPath ./build \
  -destination "id=$DEVICE_ID" \
  -allowProvisioningUpdates \
  build 2>&1 | tee "$TEST_DIR/build_log.txt"

BUILD_STATUS=${PIPESTATUS[0]}
if [ $BUILD_STATUS -ne 0 ]; then
    echo -e "${RED}❌ Build failed! Check $TEST_DIR/build_log.txt for details${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Build successful${NC}\n"

# Find the built app
echo -e "${BLUE}📦 Locating built app...${NC}"
APP_PATH=$(find ./build/Build/Products/Debug-iphoneos -name "HiveScribeiOS.app" | head -1)
if [ -z "$APP_PATH" ]; then
    echo -e "${RED}❌ Could not find built app${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Found app at: $APP_PATH${NC}\n"

# Install the app
echo -e "${BLUE}📲 Installing app on device...${NC}"
xcrun devicectl device install app --device "$DEVICE_ID" "$APP_PATH" 2>&1 | tee "$TEST_DIR/install_log.txt"
INSTALL_STATUS=${PIPESTATUS[0]}
if [ $INSTALL_STATUS -ne 0 ]; then
    echo -e "${RED}❌ Installation failed! Check $TEST_DIR/install_log.txt for details${NC}"
    exit 1
fi
echo -e "${GREEN}✅ App installed successfully${NC}\n"

# Clear old crash logs
echo -e "${BLUE}🗑️  Clearing old crash logs...${NC}"
# Note: We can't actually delete crash logs, but we'll timestamp this for reference
echo "Test started at: $(date)" > "$TEST_DIR/test_start_marker.txt"

# Start log streaming in background
echo -e "${BLUE}📝 Starting log capture...${NC}"
xcrun devicectl device log stream --device "$DEVICE_ID" \
  --predicate 'subsystem == "com.hiveguide.audio" OR processImagePath CONTAINS "HiveScribe" OR senderImagePath CONTAINS "HiveScribe"' \
  > "$TEST_DIR/runtime_log.txt" 2>&1 &
LOG_PID=$!
echo -e "${GREEN}✅ Logging started (PID: $LOG_PID)${NC}\n"

# Give logs a moment to start
sleep 2

# Launch the app
echo -e "${BLUE}🚀 Launching app...${NC}"
BUNDLE_ID="org.reactjs.native.example.HiveScribeiOS"

# Try to launch - this will fail if app crashes, which is useful
xcrun devicectl device process launch --device "$DEVICE_ID" "$BUNDLE_ID" 2>&1 | tee "$TEST_DIR/launch_log.txt" || true
echo -e "${GREEN}✅ Launch command sent${NC}\n"

# Wait for app to initialize and potentially crash
echo -e "${BLUE}⏱️  Waiting 10 seconds for app to initialize...${NC}"
for i in {10..1}; do
    echo -ne "   ${YELLOW}$i seconds remaining...${NC}\r"
    sleep 1
done
echo -e "\n"

# Stop log capture
echo -e "${BLUE}🛑 Stopping log capture...${NC}"
kill $LOG_PID 2>/dev/null || true
sleep 1
echo -e "${GREEN}✅ Logs captured${NC}\n"

# Take screenshot
echo -e "${BLUE}📸 Taking screenshot...${NC}"
xcrun devicectl device info screenshot --device "$DEVICE_ID" "$TEST_DIR/screenshot.png" 2>&1 || \
    echo -e "${YELLOW}⚠️  Could not capture screenshot (device may be locked)${NC}"

# Check for crashes
echo -e "\n${BLUE}🔍 Checking for crash reports...${NC}"
CRASH_LIST="$TEST_DIR/crash_list.txt"
xcrun devicectl device info crashlogs list --device "$DEVICE_ID" 2>&1 | tee "$CRASH_LIST"

# Look for recent HiveScribe crashes
if grep -i "hiveguide" "$CRASH_LIST" | head -5 > "$TEST_DIR/recent_crashes.txt"; then
    echo -e "${RED}❌ CRASH DETECTED!${NC}\n"

    # Get the most recent crash
    CRASH_NAME=$(grep -i "hiveguide" "$CRASH_LIST" | head -1 | awk '{print $1}')

    if [ ! -z "$CRASH_NAME" ]; then
        echo -e "${BLUE}📄 Fetching crash report: $CRASH_NAME${NC}"
        xcrun devicectl device info crashlogs show --device "$DEVICE_ID" "$CRASH_NAME" > "$TEST_DIR/crash_report.txt" 2>&1

        # Extract key crash info
        echo -e "\n${RED}═══════════════════════════════════════${NC}"
        echo -e "${RED}           CRASH SUMMARY${NC}"
        echo -e "${RED}═══════════════════════════════════════${NC}"

        grep -A 5 "Exception Type:" "$TEST_DIR/crash_report.txt" || echo "Could not parse crash type"
        echo ""
        grep -A 10 "Thread.*Crashed:" "$TEST_DIR/crash_report.txt" | head -15 || echo "Could not parse crash thread"

        echo -e "\n${YELLOW}Full crash report saved to:${NC}"
        echo -e "${YELLOW}$TEST_DIR/crash_report.txt${NC}\n"
    fi
else
    echo -e "${GREEN}✅ No crashes detected${NC}\n"
fi

# Analyze runtime logs for errors
echo -e "${BLUE}🔍 Analyzing runtime logs...${NC}"
if [ -f "$TEST_DIR/runtime_log.txt" ]; then
    # Look for errors and important audio-related messages
    grep -i "error\|fail\|exception\|crash\|audio" "$TEST_DIR/runtime_log.txt" > "$TEST_DIR/filtered_errors.txt" 2>/dev/null || \
        echo "No errors found in logs"

    if [ -s "$TEST_DIR/filtered_errors.txt" ]; then
        echo -e "${YELLOW}⚠️  Found potential issues in logs:${NC}"
        head -20 "$TEST_DIR/filtered_errors.txt"
        echo ""
        echo -e "${YELLOW}Full filtered log saved to:${NC}"
        echo -e "${YELLOW}$TEST_DIR/filtered_errors.txt${NC}\n"
    else
        echo -e "${GREEN}✅ No obvious errors in runtime logs${NC}\n"
    fi
fi

# Generate summary report
echo -e "${BLUE}📊 Generating test summary...${NC}"
SUMMARY_FILE="$TEST_DIR/TEST_SUMMARY.txt"

cat > "$SUMMARY_FILE" << EOF
HiveScribe iOS Audio Test Report
================================
Date: $(date)
Device: $DEVICE_NAME
Device ID: $DEVICE_ID

Build Status: $([ $BUILD_STATUS -eq 0 ] && echo "SUCCESS" || echo "FAILED")
Install Status: $([ $INSTALL_STATUS -eq 0 ] && echo "SUCCESS" || echo "FAILED")

Crashes Detected: $(grep -i "hiveguide" "$CRASH_LIST" 2>/dev/null | wc -l | xargs)

Files Generated:
- build_log.txt          : Xcode build output
- install_log.txt        : App installation log
- launch_log.txt         : App launch log
- runtime_log.txt        : Runtime logs from device
- filtered_errors.txt    : Filtered error messages
- screenshot.png         : Screenshot of app state
- crash_report.txt       : Detailed crash report (if crash occurred)
- crash_list.txt         : List of all crash logs on device

Test Location: $TEST_DIR
EOF

echo -e "${GREEN}✅ Summary generated${NC}\n"

# Final output
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}         TEST COMPLETE${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "\n${BLUE}📁 All results saved to:${NC}"
echo -e "${BLUE}$TEST_DIR${NC}\n"

echo -e "${YELLOW}Quick access to key files:${NC}"
echo -e "Summary:    open $TEST_DIR/TEST_SUMMARY.txt"
echo -e "Screenshot: open $TEST_DIR/screenshot.png"
echo -e "Logs:       open $TEST_DIR/runtime_log.txt"
if [ -f "$TEST_DIR/crash_report.txt" ]; then
    echo -e "Crash:      open $TEST_DIR/crash_report.txt"
fi

echo -e "\n${BLUE}💡 Next steps:${NC}"
if [ -f "$TEST_DIR/crash_report.txt" ]; then
    echo -e "1. Review crash report at: $TEST_DIR/crash_report.txt"
    echo -e "2. Check filtered errors at: $TEST_DIR/filtered_errors.txt"
    echo -e "3. Look for stack trace with AudioStreamingModule"
else
    echo -e "1. Check screenshot at: $TEST_DIR/screenshot.png"
    echo -e "2. Review runtime logs at: $TEST_DIR/runtime_log.txt"
    echo -e "3. Verify app is functioning as expected"
fi

echo ""
