#!/bin/bash

# HiveGuide Deployment Script for Railway
# This script ensures the frontend is built and copied to static/ directory

echo "🐝 HiveGuide Deployment Script"
echo "==============================="

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run this script from the project root."
    exit 1
fi

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

# Build the frontend
echo "🔨 Building frontend..."
npm run build

# Go back to project root
cd ..

# Ensure static directory exists
echo "📁 Ensuring static directory exists..."
mkdir -p static

# Copy built frontend to static directory
echo "📋 Copying built frontend to static directory..."
cp -r frontend/dist/* static/

# Verify the files were copied
echo "✅ Verifying deployment..."
if [ -f "static/index.html" ] && [ -d "static/assets" ]; then
    echo "✅ Frontend successfully deployed to static/ directory"
    echo "🚀 Ready for Railway deployment!"
    
    # Show the asset files that were created
    echo ""
    echo "📄 Static files:"
    ls -la static/
    echo ""
    echo "🎨 Asset files:"
    ls -la static/assets/
else
    echo "❌ Error: Frontend deployment failed"
    exit 1
fi

echo ""
echo "🎯 Next steps for Railway:"
echo "1. Commit and push these changes to your repository"
echo "2. Railway will automatically deploy using the Procfile"
echo "3. The app will serve the React frontend with proper styling"