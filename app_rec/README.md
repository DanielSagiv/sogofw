# SOGOFW Multi-Camera Recording System

A Python-based multi-sensor data acquisition system for Raspberry Pi 5 with:
- 2x RPi cameras (via rpicam-vid)
- 1x DepthAI camera (with integrated IMU)
- GPS module (NMEA)
- Skeleton recognition (MediaPipe)
- LCD display (Grove RGB LCD)
- Physical button control

## 🚀 Quick Setup for Raspberry Pi 5

### 1. System Update
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git
```

### 2. Install Camera Dependencies
```bash
# Enable camera interface
sudo raspi-config nonint do_camera 0

# Install camera tools
sudo apt install -y rpicam-apps

# Reboot to enable camera
sudo reboot
```

### 3. Install GPIO Libraries
```bash
# Install GPIO libraries
sudo apt install -y python3-gpiozero python3-rpi.gpio python3-lgpio gpiod libgpiod-dev

# Add user to gpio group
sudo usermod -a -G gpio $USER
```

### 4. Install DepthAI
```bash
# Install DepthAI dependencies
sudo apt install -y cmake build-essential libssl-dev

# Install DepthAI Python package
pip3 install depthai
```

### 5. Install Python Dependencies
```bash
# Navigate to project directory
cd ~/sogofw/app_rec

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install opencv-python mediapipe protobuf pyserial smbus2
```

### 6. Hardware Setup

#### Camera Connections
- **RPi Camera 1**: Connect to CSI0 port
- **RPi Camera 2**: Connect to CSI1 port  
- **DepthAI Camera**: Connect via USB

#### GPS Module
- Connect GPS module to USB port (appears as `/dev/ttyUSB0`)
- Test with: `sudo cat /dev/ttyUSB0`

#### LCD Display (Optional)
- Connect Grove RGB LCD to I2C pins (SDA/SCL)
- Enable I2C: `sudo raspi-config nonint do_i2c 0`

#### Physical Button (Optional)
- Connect button to GPIO 17 (Pin 11)
- Test with: `gpiozero-test-button 17`

### 7. Test Individual Components

#### Test Cameras
```bash
# Test RPi cameras
rpicam-vid --camera 1 --output test1.h264
rpicam-vid --output test2.h264

# Test DepthAI
python3 -c "import depthai as dai; print('DepthAI OK')"
```

#### Test GPS
```bash
# Check if GPS device exists
ls /dev/ttyUSB*

# Test GPS data
sudo cat /dev/ttyUSB0
```

#### Test GPIO
```bash
# Test button
python3 -c "from gpiozero import Button; b = Button(17); print('GPIO OK')"
```

### 8. Run the Application

#### Option A: No GPIO (Keyboard Control)
```bash
cd ~/sogofw/app_rec
source venv/bin/activate
python3 main_no_gpio.py
```
- Press Enter to start/stop recording
- Press Ctrl+C to exit

#### Option B: With Physical Button
```bash
cd ~/sogofw/app_rec
source venv/bin/activate
python3 rec_vid_btn.py
```
- Press physical button to start/stop recording

### 9. Troubleshooting

#### Camera Issues
```bash
# Check camera status
vcgencmd get_camera

# List camera devices
ls /dev/video*

# Test camera permissions
sudo usermod -a -G video $USER
```

#### GPIO Issues
```bash
# Check GPIO permissions
groups $USER

# Test GPIO access
echo 17 | sudo tee /sys/class/gpio/export
echo in | sudo tee /sys/class/gpio/gpio17/direction
cat /sys/class/gpio/gpio17/value
```

#### DepthAI Issues
```bash
# Check USB devices
lsusb | grep DepthAI

# Test DepthAI connection
python3 -c "import depthai as dai; device = dai.Device(); print('Connected')"
```

#### GPS Issues
```bash
# Check serial ports
ls /dev/tty*

# Test GPS with different baud rates
sudo cat /dev/ttyUSB0
sudo cat /dev/ttyACM0
```

### 10. Recording Output

Recordings are saved in `~/sogofw/app_rec/recordings/`:
- `camera1_YYYYMMDD_HHMMSS.mp4` - RPi Camera 1 (converted from MJPEG)
- `camera2_YYYYMMDD_HHMMSS.mp4` - RPi Camera 2 (converted from MJPEG)  
- `camera3_YYYYMMDD_HHMMSS.avi` - DepthAI Camera
- `imu_YYYYMMDD_HHMMSS.json` - IMU data
- `skeleton_YYYYMMDD_HHMMSS.json` - Skeleton data
- `gps_YYYYMMDD_HHMMSS.json` - GPS data

**Note**: RPi cameras record in MJPEG format and are automatically converted to MP4 using ffmpeg.

### 11. System Service (Optional)

Create systemd service for auto-start:
```bash
sudo nano /etc/systemd/system/sogofw.service
```

Add content:
```ini
[Unit]
Description=SOGOFW Recording System
After=network.target

[Service]
Type=simple
User=sagiv
WorkingDirectory=/home/sagiv/sogofw/app_rec
Environment=PATH=/home/sagiv/sogofw/app_rec/venv/bin
ExecStart=/home/sagiv/sogofw/app_rec/venv/bin/python3 main_no_gpio.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable service:
```bash
sudo systemctl enable sogofw.service
sudo systemctl start sogofw.service
```

## 📋 Requirements Checklist

- [ ] Raspberry Pi 5 with latest OS
- [ ] 2x RPi cameras connected
- [ ] DepthAI camera connected via USB
- [ ] GPS module connected
- [ ] LCD display connected (optional)
- [ ] Physical button connected (optional)
- [ ] All Python dependencies installed
- [ ] GPIO libraries installed
- [ ] Camera interface enabled
- [ ] I2C enabled (for LCD)
- [ ] User added to gpio and video groups

## 🆘 Common Issues

1. **"No module named 'depthai'"** → Install DepthAI: `pip3 install depthai`
2. **"Permission denied" for GPIO** → Add user to gpio group and reboot
3. **"Camera not found"** → Enable camera interface in raspi-config
4. **"GPS device not found"** → Check USB connection and device name
5. **"LCD not working"** → Enable I2C interface in raspi-config

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify all hardware connections
3. Test individual components
4. Check system logs: `journalctl -u sogofw.service` 