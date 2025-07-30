#!/bin/bash

echo "Setting up Python Multi-Camera Recording System..."

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    git \
    libgpiod-dev \
    python3-gpiozero \
    python3-rpi.gpio \
    python3-lgpio

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create recordings directory
echo "Creating recordings directory..."
mkdir -p recordings

# Set up GPIO permissions
echo "Setting up GPIO permissions..."
sudo usermod -a -G gpio $USER
sudo usermod -a -G dialout $USER

# Create udev rules for GPIO
echo "Creating udev rules..."
sudo tee /etc/udev/rules.d/99-gpio.rules > /dev/null <<EOF
SUBSYSTEM=="gpio", GROUP="gpio", MODE="0660"
SUBSYSTEM=="bcm2835-gpiomem", GROUP="gpio", MODE="0660"
SUBSYSTEM=="gpiochip*", GROUP="gpio", MODE="0660"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Install additional GPIO libraries
echo "Installing additional GPIO libraries..."
pip install RPi.GPIO
pip install lgpio

echo "Setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "source venv/bin/activate"
echo ""
echo "To run the application:"
echo "python main.py"
echo ""
echo "To test the button:"
echo "python -c \"from gpiozero import Button, LED; from signal import pause; button = Button(17); led = LED(27); button.when_pressed = led.on; button.when_released = led.off; pause()\""
echo ""
echo "If GPIO still doesn't work, try running as root:"
echo "sudo python main.py" 