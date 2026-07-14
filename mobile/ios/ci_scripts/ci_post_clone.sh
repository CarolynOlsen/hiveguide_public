#!/bin/sh

# Xcode Cloud post-clone script
# This runs after the repository is cloned and sets up dependencies
# Located in mobile/ios/ci_scripts/ (relative to workspace)

set -e

echo "🔧 Setting up build environment for Xcode Cloud..."
echo "Current directory: $(pwd)"
echo "Repository root: $CI_WORKSPACE"

# Navigate to repository root first
if [ -n "$CI_WORKSPACE" ]; then
    cd "$CI_WORKSPACE"
    echo "Changed to repository root: $(pwd)"
else
    # Fallback: go up from script location (mobile/ios/ci_scripts/)
    cd "$(dirname "$0")/../../.."
    echo "Changed to repository root (fallback): $(pwd)"
fi

# Install Node.js via Homebrew (if not already available)
if ! command -v node &> /dev/null; then
    echo "📦 Installing Node.js via Homebrew..."
    if brew install node@20 2>&1 | tee /tmp/node_install.log; then
        # node@20 is keg-only, so add it to PATH
        export PATH="/usr/local/opt/node@20/bin:$PATH"
        echo "✅ Added node@20 to PATH"
    elif brew link --overwrite node@20 2>&1; then
        export PATH="/usr/local/opt/node@20/bin:$PATH"
    elif brew install node 2>&1; then
        # Regular node installation should be in PATH automatically
        echo "✅ Installed regular node"
    else
        echo "❌ Error: Node.js installation failed"
        exit 1
    fi
fi

# Check for node@20 in common Homebrew locations and add to PATH if found
if ! command -v node &> /dev/null; then
    if [ -d "/usr/local/opt/node@20/bin" ]; then
        export PATH="/usr/local/opt/node@20/bin:$PATH"
        echo "✅ Found node@20, added to PATH"
    elif [ -d "/opt/homebrew/opt/node@20/bin" ]; then
        export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
        echo "✅ Found node@20 (Apple Silicon), added to PATH"
    fi
fi

# Verify Node.js is available
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js not found in PATH"
    echo "Checking for node installations:"
    ls -la /usr/local/opt/node* 2>/dev/null || true
    ls -la /opt/homebrew/opt/node* 2>/dev/null || true
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
