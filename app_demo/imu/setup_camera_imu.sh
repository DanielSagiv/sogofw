#!/bin/bash

# Camera IMU Setup Script
# This script helps set up the camera IMU integration

set -e

echo "=== Camera IMU Setup Script ==="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root. Some operations may not work correctly."
    echo ""
fi

# Function to check command availability
check_command() {
    if command -v $1 &> /dev/null; then
        echo "✓ $1 is installed"
        return 0
    else
        echo "✗ $1 is not installed"
        return 1
    fi
}

# Function to install Python package
install_python_package() {
    echo "Installing $1..."
    if pip3 install $1; then
        echo "✓ $1 installed successfully"
    else
        echo "✗ Failed to install $1"
        return 1
    fi
}

echo "1. Checking system dependencies..."

# Check Python
if ! check_command python3; then
    echo "Python3 is required but not installed. Please install it first."
    exit 1
fi

# Check pip
if ! check_command pip3; then
    echo "Installing pip3..."
    sudo apt update
    sudo apt install -y python3-pip
fi

# Check build tools
if ! check_command make; then
    echo "Installing build tools..."
    sudo apt update
    sudo apt install -y build-essential
fi

# Check pkg-config
if ! check_command pkg-config; then
    echo "Installing pkg-config..."
    sudo apt update
    sudo apt install -y pkg-config
fi

echo ""
echo "2. Checking Python dependencies..."

# Check if depthai is installed
if python3 -c "import depthai" 2>/dev/null; then
    echo "✓ depthai is installed"
else
    echo "Installing depthai..."
    install_python_package depthai
fi

# Check if opencv is installed
if python3 -c "import cv2" 2>/dev/null; then
    echo "✓ opencv-python is installed"
else
    echo "Installing opencv-python..."
    install_python_package opencv-python
fi

echo ""
echo "3. Checking USB permissions..."

# Check if user is in video group
if groups $USER | grep -q video; then
    echo "✓ User is in video group"
else
    echo "Adding user to video group..."
    sudo usermod -a -G video $USER
    echo "Please log out and log back in for group changes to take effect"
fi

# Check if udev rules exist for DepthAI
if [ -f "/etc/udev/rules.d/99-depthai.rules" ]; then
    echo "✓ DepthAI udev rules exist"
else
    echo "Creating DepthAI udev rules..."
    sudo tee /etc/udev/rules.d/99-depthai.rules > /dev/null <<EOF
# DepthAI camera rules
SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", ATTRS{idProduct}=="2485", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", ATTRS{idProduct}=="f63b", MODE="0666"
EOF
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi

echo ""
echo "4. Testing camera connection..."

# Check if DepthAI camera is connected
if lsusb | grep -q "03e7"; then
    echo "✓ DepthAI camera detected"
else
    echo "⚠ No DepthAI camera detected. Please connect your camera."
    echo "   This is normal if you don't have the camera connected yet."
fi

echo ""
echo "5. Testing IMU functionality..."

# Test the Python script
if [ -f "test_camera_imu.py" ]; then
    echo "Testing camera IMU (will run for 5 seconds)..."
    timeout 5s python3 test_camera_imu.py || {
        echo "⚠ IMU test failed or timed out. This is normal if no camera is connected."
        echo "   The test will work once you connect a DepthAI camera."
    }
else
    echo "⚠ test_camera_imu.py not found in current directory"
fi

echo ""
echo "6. Building the application..."

# Go to parent directory and build
cd ..
if [ -f "Makefile" ]; then
    echo "Building application..."
    make clean
    if make all; then
        echo "✓ Application built successfully"
    else
        echo "✗ Build failed. Check the error messages above."
        exit 1
    fi
else
    echo "⚠ Makefile not found in parent directory"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Connect your DepthAI camera with integrated IMU"
echo "2. Test the IMU: cd imu && python3 test_camera_imu.py"
echo "3. Run the application: cd .. && ./app_demo"
echo ""
echo "For troubleshooting, see CAMERA_IMU_README.md" 