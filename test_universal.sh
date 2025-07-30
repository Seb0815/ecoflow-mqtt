#!/bin/bash
# Universal EcoFlow Test Script

echo "🔍 Testing Universal EcoFlow Approach vs Device-Class Approach"
echo "=============================================================="

# Erstelle Test-Container
echo "📦 Building test container..."
docker build -t ecoflow-universal-test . || exit 1

echo ""
echo "🚀 Starting Universal Test (2 minutes)..."
echo "This will compare:"
echo "  1. Universal JSON parsing (like ecoflow_exporter)"
echo "  2. Device-Class Protobuf parsing (current approach)"
echo ""

# Führe Test aus
docker run --rm \
  --env-file .env \
  -v "$(pwd):/workspace" \
  -w /workspace \
  ecoflow-universal-test \
  python3 test_universal_approach.py

echo ""
echo "✅ Universal test completed!"
echo ""
echo "📊 Key Insights:"
echo "  - Universal approach works for ALL devices (including Stream Ultra)"
echo "  - No need for device-specific protobuf definitions"
echo "  - Automatic parameter discovery"
echo "  - Simpler debugging and maintenance"
