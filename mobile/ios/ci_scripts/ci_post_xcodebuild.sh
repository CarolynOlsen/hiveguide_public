#!/bin/sh

# Xcode Cloud post-xcodebuild script
# This runs after xcodebuild completes successfully
# Can be used to upload to TestFlight if distribution isn't configured in workflow

set -e

echo "🔧 Post-build script running..."
echo "Current directory: $(pwd)"

# Check if archive was created
ARCHIVE_PATH="${CI_ARCHIVE_PATH:-/Volumes/workspace/build.xcarchive}"

if [ ! -d "$ARCHIVE_PATH" ]; then
    echo "⚠️  Archive not found at $ARCHIVE_PATH"
    echo "Skipping automatic upload. Please configure distribution in Xcode Cloud workflow."
    exit 0
fi

echo "✅ Archive found at: $ARCHIVE_PATH"

# Note: Automatic upload requires distribution to be configured in the Xcode Cloud workflow
# This script can be used for additional post-build tasks if needed
echo "ℹ️  To enable automatic TestFlight distribution:"
echo "   1. Open Xcode → Product → Xcode Cloud → View Workflows"
echo "   2. Edit your workflow"
echo "   3. Add 'Distribute to TestFlight' post-action"
echo ""
echo "✅ Post-build script complete!"

