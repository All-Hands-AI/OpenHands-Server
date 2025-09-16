#!/bin/bash

# Build script for OpenHands Server
# Based on OpenHands-CLI build script

set -e

echo "Installing dependencies..."
uv sync --extra dev

# Run the build
echo "Running PyInstaller..."
uv run python openhands_server/sdk_server/build.py

echo "Build complete!"
echo "Binary location: dist/openhands-server"
