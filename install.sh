#!/bin/bash
# ADS-B ASCII Art Radar - Installation Script

echo "==================================================="
echo "  ADS-B ASCII Art Radar - Installation Script"
echo "==================================================="
echo

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+')
if [ $? -ne 0 ]; then
    echo "❌ Python 3 is not installed. Please install Python 3.7 or higher."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

# Try to install pip packages if possible
echo
echo "Attempting to install Python dependencies..."

# Check if we can install packages
if command -v pip3 >/dev/null 2>&1; then
    echo "Found pip3, installing dependencies..."
    pip3 install -r requirements.txt --user
    if [ $? -eq 0 ]; then
        echo "✅ Dependencies installed successfully"
    else
        echo "⚠️  Some dependencies may not have installed, but the app should still work"
    fi
else
    echo "⚠️  pip3 not available. The app will use fallback methods for missing dependencies."
fi

# Make main script executable
chmod +x main.py

echo
echo "==================================================="
echo "  Installation Complete!"
echo "==================================================="
echo
echo "Try the demo mode:"
echo "  python3 main.py --demo"
echo
echo "For live ADS-B data (requires dump1090 or similar):"
echo "  python3 main.py --url http://your-adsb-source:8080/data/aircraft.json"
echo
echo "Different ASCII styles:"
echo "  python3 main.py --demo --style detailed"
echo "  python3 main.py --demo --style classic"
echo
echo "See README.md for full documentation!"
echo
