#!/bin/sh

# Xcode Cloud post-clone script
# This runs after the repository is cloned and sets up dependencies

set -e

echo "🔧 Setting up build environment for Xcode Cloud..."
echo "Current directory: $(pwd)"
echo "Repository root: $CI_WORKSPACE"

# Install Node.js via Homebrew (if not already available)
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js via Homebrew..."
    brew install node@20 || brew link --overwrite node@20 || brew install node
fi

# Verify Node.js is available
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js installation failed"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"
echo "✅ npm version: $(npm --version)"

# Navigate to mobile directory and install npm dependencies
echo "📦 Installing npm dependencies..."
cd mobile || { echo "❌ Error: mobile directory not found"; exit 1; }
echo "Current directory: $(pwd)"
npm ci || { echo "❌ Error: npm ci failed"; exit 1; }

# Install CocoaPods dependencies
echo "☕ Installing CocoaPods dependencies..."
cd ios || { echo "❌ Error: mobile/ios directory not found"; exit 1; }
echo "Current directory: $(pwd)"
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Install CocoaPods if not available
if ! command -v pod &> /dev/null; then
    echo "📦 Installing CocoaPods..."
    brew install cocoapods || gem install cocoapods || { echo "❌ Error: CocoaPods installation failed"; exit 1; }
fi

echo "✅ CocoaPods version: $(pod --version)"

# Verify Podfile exists
if [ ! -f "Podfile" ]; then
    echo "❌ Error: Podfile not found in $(pwd)"
    exit 1
fi

echo "Running pod install..."
pod install || { echo "❌ Error: pod install failed"; exit 1; }

# Verify Pods directory was created
if [ ! -d "Pods" ]; then
    echo "❌ Error: Pods directory was not created"
    exit 1
fi

echo "✅ Pods directory exists"
echo "Pods directory contents:"
ls -la Pods/ | head -10
echo ""
echo "Checking for Target Support Files:"
if [ -d "Pods/Target Support Files/Pods-HiveGuideiOS" ]; then
    echo "✅ Target Support Files directory exists"
    ls -la "Pods/Target Support Files/Pods-HiveGuideiOS/" | head -10
else
    echo "❌ Warning: Target Support Files directory not found"
fi
echo ""
echo "✅ Environment setup complete!"
