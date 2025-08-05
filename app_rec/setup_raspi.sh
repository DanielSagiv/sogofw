#!/bin/bash

echo "🚀 SOGOFW Raspberry Pi 5 Setup Script"
echo "======================================"

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "❌ This script should be run on a Raspberry Pi"
    exit 1
fi

echo "✅ Running on Raspberry Pi"

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install basic dependencies
echo "📦 Installing basic dependencies..."
sudo apt install -y python3-pip python3-venv git cmake build-essential libssl-dev

# Install camera tools
echo "📷 Installing camera tools..."
sudo apt install -y rpicam-apps

# Enable camera interface
echo "📷 Enabling camera interface..."
sudo raspi-config nonint do_camera 0

# Install GPIO libraries
echo "🔌 Installing GPIO libraries..."
sudo apt install -y python3-gpiozero python3-rpi.gpio python3-lgpio gpiod libgpiod-dev

# Add user to gpio group
echo "🔌 Adding user to gpio group..."
sudo usermod -a -G gpio $USER

# Enable I2C (for LCD)
echo "📺 Enabling I2C interface..."
sudo raspi-config nonint do_i2c 0

# Install DepthAI
echo "🤖 Installing DepthAI..."
pip3 install depthai

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
cd ~/sogofw/app_rec
python3 -m venv venv

# Activate virtual environment and install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install opencv-python mediapipe protobuf pyserial smbus2

# Create recordings directory
echo "📁 Creating recordings directory..."
mkdir -p recordings

# Set permissions
echo "🔐 Setting permissions..."
chmod +x *.py
chmod +x *.sh

echo ""
echo "✅ Setup completed!"
echo ""
echo "🔧 Next steps:"
echo "1. Reboot your Raspberry Pi: sudo reboot"
echo "2. Test cameras: rpicam-vid --camera 1 --output test1.h264"
echo "3. Test DepthAI: python3 -c 'import depthai as dai; print(\"OK\")'"
echo "4. Test GPS: sudo cat /dev/ttyUSB0"
echo "5. Run the application: source venv/bin/activate && python3 main_no_gpio.py"
echo ""
echo "📖 For detailed instructions, see README.md" 