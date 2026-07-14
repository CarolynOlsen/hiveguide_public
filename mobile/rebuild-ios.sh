#!/bin/bash

# HiveGuide iOS Rebuild and Reinstall Script
# This script ensures a completely clean build with no cached JavaScript

set -e  # Exit on any error

echo "🐝 HiveGuide iOS Rebuild Script"
echo "=================================="
echo ""
echo "This script will perform a complete clean rebuild to ensure no cached JavaScript is running."
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function for section headers
print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Check if we're in the mobile directory
if [ ! -f "package.json" ] || [ ! -d "ios" ]; then
    echo -e "${RED}❌ Error: This script must be run from the mobile/ directory${NC}"
    echo "Usage: cd mobile && ./rebuild-ios.sh"
    exit 1
fi

# Step 1: Kill Metro bundler processes
print_section "📦 Step 1/8: Killing Metro Bundler Processes"
echo "Stopping any running Metro bundler processes..."
pkill -f "react-native" || true
pkill -f "metro" || true
# Also kill node processes that might be Metro
lsof -ti:8081 | xargs kill -9 2>/dev/null || true
echo -e "${GREEN}✅ Metro processes stopped${NC}"

# Step 2: Clean Metro cache
print_section "🧹 Step 2/8: Cleaning Metro Cache"
echo "Removing Metro bundler cache..."
rm -rf /tmp/metro-* 2>/dev/null || true
rm -rf /tmp/haste-* 2>/dev/null || true
rm -rf $TMPDIR/react-* 2>/dev/null || true
rm -rf $TMPDIR/metro-* 2>/dev/null || true
echo "Removing node_modules/.cache..."
rm -rf node_modules/.cache 2>/dev/null || true
echo "Clearing additional React Native caches..."
rm -rf ~/.cache/react-native-community 2>/dev/null || true
rm -rf ~/Library/Caches/React\ Native 2>/dev/null || true
rm -rf ~/Library/Developer/Xcode/DerivedData/*/Build/Products/Debug-iphonesimulator/*.app/main.jsbundle 2>/dev/null || true
echo "Clearing Watchman cache..."
watchman watch-del-all 2>/dev/null || echo "Watchman not installed, skipping..."
echo -e "${GREEN}✅ Metro cache cleaned thoroughly${NC}"

# Step 3: Clean iOS build artifacts
print_section "🏗️  Step 3/8: Cleaning iOS Build Artifacts"
echo "Cleaning Xcode build folder..."
cd ios
xcodebuild clean -workspace HiveGuideiOS.xcworkspace -scheme HiveGuideiOS 2>/dev/null || true
echo "Removing DerivedData..."
rm -rf ~/Library/Developer/Xcode/DerivedData/HiveGuideiOS-* 2>/dev/null || true
rm -rf build/ 2>/dev/null || true
echo -e "${GREEN}✅ iOS build artifacts cleaned${NC}"
cd ..

# Step 4: Clean CocoaPods
print_section "☕ Step 4/8: Cleaning CocoaPods"
echo "Removing Pods and Podfile.lock..."
cd ios
rm -rf Pods 2>/dev/null || true
rm -f Podfile.lock 2>/dev/null || true
pod cache clean --all 2>/dev/null || true
echo -e "${GREEN}✅ CocoaPods cleaned${NC}"
cd ..

# Step 5: Clean node_modules and package locks
print_section "📦 Step 5/8: Cleaning Node Modules"
echo "Removing node_modules..."
rm -rf node_modules 2>/dev/null || true
rm -f package-lock.json 2>/dev/null || true
echo -e "${GREEN}✅ Node modules cleaned${NC}"

# Step 6: Reinstall dependencies
print_section "⬇️  Step 6/8: Reinstalling Dependencies"
echo "Installing npm packages..."
npm install
echo ""
echo "Installing CocoaPods..."
cd ios
pod install
cd ..
echo -e "${GREEN}✅ Dependencies installed${NC}"

# Step 7: Start Metro bundler
print_section "🚀 Step 7/8: Starting Metro Bundler"
echo "Starting Metro bundler with complete cache reset..."
echo ""

# Ensure no stale metro processes and clear additional caches
pkill -f "react-native" || true
pkill -f "metro" || true
rm -rf /tmp/metro-* 2>/dev/null || true

# Start Metro in background with aggressive cache clearing
npx react-native start --reset-cache --port 8081 &
METRO_PID=$!
echo -e "${GREEN}✅ Metro started (PID: $METRO_PID)${NC}"
echo "Waiting for Metro to fully initialize and build fresh bundle..."
sleep 10

# Verify Metro is responding
echo "Verifying Metro is serving fresh bundles..."
if curl -s "http://localhost:8081/status" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Metro bundler is responding${NC}"
else
    echo -e "${YELLOW}⚠️  Metro bundler may still be starting...${NC}"
fi

# Step 8: Build and install on device if available
print_section "📱 Step 8/8: Checking for Connected iPhone"
echo "Looking for connected iOS device via USB..."

# Hardcoded UDID for Carolyn's Phone of Doom
DEVICE_UDID="00008140-000E49991E63001C"

# Check if the device is actually connected
echo "Checking if device $DEVICE_UDID is connected..."
if xcrun xctrace list devices 2>/dev/null | grep -q "$DEVICE_UDID"; then
    echo -e "${GREEN}✅ Found iOS device: $DEVICE_UDID (Carolyn's Phone of Doom)${NC}"
    echo "Building and installing app on connected iOS device..."
    echo ""
    
    cd ios
    
    # Build using workspace (more reliable than project)
    echo "🔨 Starting build process with workspace (Release configuration)..."
    echo -e "${BLUE}⏰ Build started at: $(date '+%H:%M:%S')${NC}"
    if xcodebuild -workspace HiveGuideiOS.xcworkspace \
                  -scheme HiveGuideiOS \
                  -configuration Release \
                  -allowProvisioningUpdates \
                  build > /tmp/xcodebuild_build.log 2>&1; then
        
        echo -e "${GREEN}✅ Build completed successfully!${NC}"
        echo -e "${BLUE}⏰ Build completed at: $(date '+%H:%M:%S')${NC}"
        
        # Find the built app
        APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData -name "HiveGuideiOS.app" -path "*/Release-iphoneos/*" | head -n 1)
        
        if [ -n "$APP_PATH" ] && [ -d "$APP_PATH" ]; then
            echo "📱 Installing app from: $APP_PATH"
            
            # Install the app using devicectl (more modern than older tools)
            if xcrun devicectl device install app --device "$DEVICE_UDID" "$APP_PATH" > /tmp/xcodebuild_install.log 2>&1; then
                echo -e "${GREEN}🎉 App installed successfully!${NC}"
                BUILD_STATUS=0
            else
                echo -e "${RED}❌ App installation failed${NC}"
                echo "Install log:"
                tail -10 /tmp/xcodebuild_install.log
                BUILD_STATUS=1
            fi
        else
            echo -e "${RED}❌ Could not find built app at expected location${NC}"
            BUILD_STATUS=1
        fi
    else
        echo -e "${RED}❌ Build failed${NC}"
        echo "Build log:"
        tail -20 /tmp/xcodebuild_build.log | grep -E "error:|Error|failed"
        BUILD_STATUS=1
    fi
    cd ..
    
    if [ $BUILD_STATUS -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ App successfully installed on iPhone!${NC}"
        echo ""
        echo -e "${BLUE}📱 IMPORTANT: To ensure you're running the latest code:${NC}"
        echo -e "${YELLOW}1. Force close the HiveGuide app if it's running${NC}"
        echo -e "${YELLOW}2. Open the app fresh from the home screen${NC}"
        echo -e "${YELLOW}3. If you still see old behavior, shake the device and tap 'Reload'${NC}"
        echo ""
        echo -e "${GREEN}Metro is running to serve fresh JavaScript updates.${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop Metro when done testing.${NC}"
        
        # Wait for Metro (keep script running)
        wait $METRO_PID
    else
        echo ""
        echo -e "${RED}❌ Build or installation failed. Check errors above.${NC}"
        echo -e "${YELLOW}Stopping Metro...${NC}"
        kill $METRO_PID 2>/dev/null
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  No iPhone connected via USB${NC}"
    echo ""
    echo -e "${YELLOW}Metro is running with fresh cache. To build and run the app:${NC}"
    echo ""
    echo -e "${GREEN}  Option 1: In a new terminal, run:${NC}"
    echo -e "${GREEN}    cd mobile${NC}"
    echo -e "${GREEN}    npx react-native run-ios${NC}"
    echo ""
    echo -e "${GREEN}  Option 2: Open ios/HiveGuideiOS.xcworkspace in Xcode and press Run${NC}"
    echo ""
    echo -e "${BLUE}💡 After launching, if you see old behavior in the simulator:${NC}"
    echo -e "${YELLOW}   Press Cmd+R or Cmd+D → 'Reload' to force fresh JavaScript${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop Metro when done.${NC}"
    
    # Wait for Metro (keep script running)
    wait $METRO_PID
fi
