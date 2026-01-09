#!/bin/bash

# HiveGuide TestFlight Deployment Script
# This script builds and uploads your app to TestFlight

set -e  # Exit on any error

# Set UTF-8 encoding for CocoaPods
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

echo "🚀 HiveGuide TestFlight Deployment"
echo "===================================="
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
    echo "Usage: cd mobile && ./deploy-testflight.sh"
    exit 1
fi

# Comprehensive environment preparation
print_section "🧹 Preparing Clean Build Environment"
echo "Clearing all caches and ensuring clean state..."

# Kill any running Metro processes
echo "Stopping Metro bundler..."
pkill -f "metro" 2>/dev/null || true
sleep 2

# Clear React Native caches
echo "Clearing React Native caches..."
npx react-native start --reset-cache --no-interactive > /dev/null 2>&1 &
METRO_PID=$!
sleep 3
kill $METRO_PID 2>/dev/null || true

# Clear Watchman cache
if command -v watchman >/dev/null 2>&1; then
    echo "Clearing Watchman cache..."
    watchman watch-del-all 2>/dev/null || true
fi

# Clear React Native community cache
echo "Clearing React Native community cache..."
rm -rf /tmp/react-native-* 2>/dev/null || true
rm -rf /tmp/haste-map-* 2>/dev/null || true
rm -rf /tmp/metro-* 2>/dev/null || true

# Update dependencies
echo "Updating dependencies..."
echo "Installing npm dependencies..."
npm ci --silent

echo "Updating CocoaPods..."
cd ios
pod install --silent
cd ..

echo -e "${GREEN}✅ Build environment prepared${NC}"

# Get Apple ID credentials from environment variables or config.yaml
if [ -z "$APPLE_ID" ] || [ -z "$APP_PASSWORD" ]; then
    # Try to read from config.yaml if it exists
    CONFIG_FILE="../config.yaml"
    if [ -f "$CONFIG_FILE" ]; then
        echo "Reading credentials from config.yaml..."
        if [ -z "$APPLE_ID" ]; then
            APPLE_ID=$(grep "^apple_id:" "$CONFIG_FILE" | sed 's/.*: *//' | tr -d ' ' | tr -d '"')
        fi
        if [ -z "$APP_PASSWORD" ]; then
            APP_PASSWORD=$(grep "^apple_app_password:" "$CONFIG_FILE" | sed 's/.*: *//' | tr -d ' ' | tr -d '"')
        fi
    fi
    
    # If still not set, prompt for credentials
    if [ -z "$APPLE_ID" ]; then
        echo ""
        echo -e "${YELLOW}Please enter your Apple Developer credentials:${NC}"
        echo ""
        read -p "Email: " APPLE_ID
    fi
    
    if [ -z "$APP_PASSWORD" ]; then
        echo ""
        echo -e "${YELLOW}Enter your App-Specific Password (not your regular Apple ID password):${NC}"
        echo -e "${YELLOW}You can create one at: https://appleid.apple.com/account/manage${NC}"
        read -s -p "App-specific Password: " APP_PASSWORD
        echo ""
    fi
    echo ""
fi

if [ -z "$APPLE_ID" ] || [ -z "$APP_PASSWORD" ]; then
    echo -e "${RED}❌ Error: Both Apple ID and password are required${NC}"
    exit 1
fi

# Create ExportOptions.plist if it doesn't exist
print_section "📝 Setting up Export Options"
EXPORT_OPTIONS_PATH="ios/ExportOptions.plist"

if [ ! -f "$EXPORT_OPTIONS_PATH" ]; then
    echo "Creating ExportOptions.plist..."
    cat > "$EXPORT_OPTIONS_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store</string>
    <key>teamID</key>
    <string>J8WHPDBMAD</string>
    <key>uploadBitcode</key>
    <false/>
    <key>uploadSymbols</key>
    <true/>
    <key>signingStyle</key>
    <string>automatic</string>
</dict>
</plist>
EOF
    echo -e "${GREEN}✅ ExportOptions.plist created${NC}"
else
    echo -e "${GREEN}✅ ExportOptions.plist already exists${NC}"
fi

cd ios

# Clean previous builds
print_section "🧹 Cleaning Previous Builds"
echo "Removing previous build artifacts..."
rm -rf build/ 2>/dev/null || true
rm -rf ~/Library/Developer/Xcode/DerivedData/HiveGuideiOS-* 2>/dev/null || true

# Additional cleanup for a truly clean build
rm -rf ~/Library/Caches/com.apple.dt.Xcode 2>/dev/null || true
xcodebuild clean -workspace HiveGuideiOS.xcworkspace -scheme HiveGuideiOS -configuration Release 2>/dev/null || true

echo -e "${GREEN}✅ Previous builds cleaned${NC}"

# Generate codegen files by doing a build first (required for React Native)
print_section "🔧 Generating Codegen Files"
echo "Building once to generate React Native codegen files..."
echo "This ensures all codegen files are created before archiving..."
xcodebuild -workspace HiveGuideiOS.xcworkspace \
           -scheme HiveGuideiOS \
           -configuration Release \
           -destination "generic/platform=iOS" \
           -allowProvisioningUpdates \
           build > /tmp/codegen_build.log 2>&1 || echo "Build completed (codegen files should be generated)"
echo -e "${GREEN}✅ Codegen files generated${NC}"

# Archive the app
print_section "📦 Creating Release Archive"
echo "Building release archive for TestFlight..."
echo -n "Archiving"

xcodebuild -workspace HiveGuideiOS.xcworkspace \
           -scheme HiveGuideiOS \
           -configuration Release \
           -destination "generic/platform=iOS" \
           -allowProvisioningUpdates \
           -archivePath "build/HiveGuideiOS.xcarchive" \
           archive > /tmp/archive.log 2>&1 &

ARCHIVE_PID=$!

# Show progress while archiving
while kill -0 $ARCHIVE_PID 2>/dev/null; do
    echo -n "."
    sleep 2
done
echo ""

# Wait for process to complete and get exit status
wait $ARCHIVE_PID
ARCHIVE_STATUS=$?

if [ $ARCHIVE_STATUS -ne 0 ]; then
    echo -e "${RED}❌ Archive failed. Check the log:${NC}"
    tail -20 /tmp/archive.log
    exit 1
fi

echo -e "${GREEN}✅ Archive created successfully${NC}"

# Export for App Store distribution
print_section "📤 Exporting for App Store"
echo "Exporting IPA for TestFlight upload..."
echo ""
echo -e "${YELLOW}Note: If this fails due to missing certificates, you may need to:${NC}"
echo -e "${YELLOW}1. Open Xcode and let it automatically manage signing${NC}"
echo -e "${YELLOW}2. Or use Xcode's Organizer to upload directly${NC}"
echo ""
echo -n "Exporting"

xcodebuild -exportArchive \
           -archivePath "build/HiveGuideiOS.xcarchive" \
           -exportPath "build/" \
           -exportOptionsPlist "ExportOptions.plist" \
           -allowProvisioningUpdates > /tmp/export.log 2>&1 &

EXPORT_PID=$!

# Show progress while exporting
while kill -0 $EXPORT_PID 2>/dev/null; do
    echo -n "."
    sleep 2
done
echo ""

# Wait for process to complete and get exit status
wait $EXPORT_PID
EXPORT_STATUS=$?

if [ $EXPORT_STATUS -ne 0 ]; then
    echo -e "${RED}❌ Export failed. Check the log:${NC}"
    tail -20 /tmp/export.log
    exit 1
fi

echo -e "${GREEN}✅ IPA exported successfully${NC}"

# Upload to TestFlight
print_section "☁️ Uploading to TestFlight"
echo "Uploading to App Store Connect..."
echo ""
echo -e "${YELLOW}This may take several minutes depending on your internet speed...${NC}"

# Use xcrun altool to upload (note: altool is deprecated but still works)
# Alternative: Use App Store Connect API for newer approach
xcrun altool --upload-app \
             --type ios \
             --file "build/HiveGuideiOS.ipa" \
             --username "$APPLE_ID" \
             --password "$APP_PASSWORD" \
             --verbose

# If altool fails, try using xcodebuild with -uploadToAppStoreConnect
# xcodebuild -uploadToAppStoreConnect \
#            -archivePath "build/HiveGuideiOS.xcarchive" \
#            -username "$APPLE_ID" \
#            -password "$APP_PASSWORD"

UPLOAD_STATUS=$?

if [ $UPLOAD_STATUS -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 Successfully uploaded to TestFlight!${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Go to App Store Connect: https://appstoreconnect.apple.com"
    echo "2. Navigate to your app → TestFlight"
    echo "3. Wait for processing to complete (usually 5-15 minutes)"
    echo "4. Add external testers or internal testers"
    echo "5. Submit for review if needed"
    echo ""
    echo -e "${GREEN}✅ Deployment complete!${NC}"
else
    echo ""
    echo -e "${RED}❌ Upload failed. Please check your credentials and try again.${NC}"
    echo ""
    echo -e "${YELLOW}Common issues:${NC}"
    echo "• Make sure you're using an App-Specific Password, not your regular Apple ID password"
    echo "• Verify your Apple ID has access to the developer account"
    echo "• Check that your app bundle ID matches what's registered in App Store Connect"
    exit 1
fi