#!/bin/bash

echo "Setting up Raspberry Pi 5 dependencies for the multi-sensor recording system..."

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install basic dependencies
echo "Installing basic dependencies..."
sudo apt-get install -y \
    build-essential \
    pkg-config \
    libglib2.0-dev \
    python3-pip \
    python3-venv \
    git

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --user depthai opencv-python numpy

# Create virtual environment for the project
echo "Creating virtual environment..."
python3 -m venv ~/oak-env
source ~/oak-env/bin/activate

# Install dependencies in virtual environment
echo "Installing dependencies in virtual environment..."
pip install depthai opencv-python numpy

# Set up GPIO permissions
echo "Setting up GPIO permissions..."
sudo usermod -a -G gpio $USER

# Create udev rules for GPIO
echo "Creating udev rules..."
sudo tee /etc/udev/rules.d/99-gpio.rules > /dev/null <<EOF
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
SUBSYSTEM=="bcm2835-gpiomem", GROUP="gpio", MODE="0660"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Create recordings directory
echo "Creating recordings directory..."
mkdir -p ~/sfw/app_demo/recordings

echo "Setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "source ~/oak-env/bin/activate"
echo ""
echo "To compile the project, run:"
echo "cd ~/sfw/app_demo && make clean && make all"
echo ""
echo "To run the application:"
echo "./app_demo" 