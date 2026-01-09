#!/bin/bash

# ==============================
# HiveGuide Local Launch Script (macOS/Linux)
# ==============================

set -e  # Exit on error

# Configuration
APP_ENTRY="main"
HOST_PORT=8000
IMAGE_NAME="hivescribe"
CONTAINER_NAME="hivescribe_container"

# Determine root directory (2 levels up from script location)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== HiveGuide Launch Script ==="
echo "Root directory: $ROOT"
echo ""

# ---- Kill existing uvicorn processes ----
echo "Checking for existing uvicorn processes..."
pkill -f "uvicorn.*main:app" || echo "No existing uvicorn processes found"
echo ""

# ---- Build the React Native Web frontend ----
echo "Building React Native Web frontend..."
cd "$ROOT/web-rn"

echo "Installing frontend dependencies..."
npm install --legacy-peer-deps

echo "Building frontend with Webpack..."
npm run build

if [ ! -d "dist" ]; then
    echo "*** ERROR: Frontend build failed – no dist/ directory found ***"
    exit 1
fi

echo "React Native Web build complete!"
echo ""

# ---- Copy built frontend to backend/static ----
echo "Deploying frontend to backend/static..."
cd "$ROOT"

# Clean existing static directory (except hive_photos and inspection_photos)
if [ -d "backend/static" ]; then
    echo "Cleaning backend/static (preserving photo directories)..."
    find backend/static -mindepth 1 -maxdepth 1 ! -name 'hive_photos' ! -name 'inspection_photos' -exec rm -rf {} +
else
    mkdir -p backend/static
fi

# Copy dist contents to static
echo "Copying web-rn/dist/* to backend/static/..."
cp -r web-rn/dist/* backend/static/

echo "React Native Web frontend deployed!"
echo ""

# ---- Verify UI strings ----
echo "Verifying UI strings in bundled JavaScript..."
if grep -r "AI Assistant" backend/static/*.js 2>/dev/null; then
    echo "⚠️  WARNING: Found 'AI Assistant' in bundled code (should be 'AI Advisor')"
else
    echo "✓ UI strings look good (no 'AI Assistant' found)"
fi
echo ""

# ---- Check for Docker ----
if command -v docker &> /dev/null; then
    echo "Docker detected – checking daemon..."
    if docker info &> /dev/null; then
        echo "Docker daemon is running – will run the app inside a container."
        echo ""
        
        # Build Docker image
        echo "Building Docker image '$IMAGE_NAME'..."
        cd "$ROOT"
        docker build -t "$IMAGE_NAME" .
        
        # Remove old container if exists
        if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            echo "Removing old container '$CONTAINER_NAME'..."
            docker rm -f "$CONTAINER_NAME" &> /dev/null
        fi
        
        # Run container
        echo "Starting container '$CONTAINER_NAME' on port $HOST_PORT..."
        docker run -d \
            --name "$CONTAINER_NAME" \
            -p "$HOST_PORT:8000" \
            -e TESSERACT_PATH=/usr/bin/tesseract \
            "$IMAGE_NAME"
        
        echo "*** SUCCESS: Container is running ***"
        echo "Access the app at http://localhost:$HOST_PORT"
        exit 0
    else
        echo "Docker CLI found but daemon is not running. Falling back to local dev."
        echo ""
    fi
fi

# ---- Fallback to local development ----
echo "Running app locally (no Docker)..."

# Activate virtual environment if present
if [ -f "$ROOT/venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source "$ROOT/venv/bin/activate"
elif [ -f "$ROOT/.venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source "$ROOT/.venv/bin/activate"
fi

# Change to root directory for proper module resolution
cd "$ROOT"

# Check if uvicorn is installed
if ! command -v uvicorn &> /dev/null; then
    echo "*** ERROR: uvicorn not found. Please install dependencies: ***"
    echo "  pip install -r backend/requirements.txt"
    exit 1
fi

# Start FastAPI server
echo ""
echo "Starting uvicorn server on port $HOST_PORT..."
echo "=== Access the app at http://127.0.0.1:$HOST_PORT ==="
echo ""

# Use exec to replace shell with uvicorn process (allows Ctrl+C to work properly)
exec uvicorn backend.main:app --reload --port "$HOST_PORT"
