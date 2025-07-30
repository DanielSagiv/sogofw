# Multi-Camera Recording System (Python)

A Python-based multi-camera recording system with IMU data collection for Raspberry Pi 5.

## Features

- **Button Control**: GPIO 17 button to start/stop recording
- **3 Cameras**: 2 RPi cameras + 1 DepthAI camera
- **IMU Data**: Gyroscope and rotation vector data from DepthAI
- **LED Indicator**: GPIO 27 LED shows recording status
- **5 Output Files**: 3 video files + 2 IMU data files

## Hardware Requirements

- Raspberry Pi 5
- 2x Raspberry Pi cameras
- 1x DepthAI OAK-D Pro Wide camera
- Button connected to GPIO 17
- LED connected to GPIO 27

## Installation

1. **Clone and setup:**
   ```bash
   cd app_rec
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

3. **Test button:**
   ```bash
   python -c "from gpiozero import Button, LED; from signal import pause; button = Button(17); led = LED(27); button.when_pressed = led.on; button.when_released = led.off; pause()"
   ```

## Usage

1. **Run the application:**
   ```bash
   python main.py
   ```

2. **Press button to start recording** - Creates 5 files:
   - `camera1_YYYYMMDD_HHMMSS.h264` - RPi camera 1 video
   - `camera2_YYYYMMDD_HHMMSS.h264` - RPi camera 2 video  
   - `camera3_YYYYMMDD_HHMMSS.avi` - DepthAI camera video
   - `imu_vector_YYYYMMDD_HHMMSS.json` - IMU rotation vector data
   - `gyroscope_YYYYMMDD_HHMMSS.json` - Gyroscope data

3. **Press button again to stop recording**

## File Structure

```
app_rec/
├── main.py              # Main application
├── requirements.txt      # Python dependencies
├── setup.sh            # Setup script
├── README.md           # This file
├── venv/               # Virtual environment
└── recordings/         # Output files directory
```

## Advantages over C Version

- ✅ **Simpler GPIO handling** - `gpiozero` library
- ✅ **Better camera integration** - Direct DepthAI Python API
- ✅ **Easier IMU handling** - Native Python JSON processing
- ✅ **No compilation issues** - Pure Python
- ✅ **Faster development** - No C compilation cycles
- ✅ **Better error handling** - Python exceptions
- ✅ **Easier to modify** - More readable and maintainable

## Troubleshooting

### Button not working
```bash
# Test button outside virtual environment
python3 -c "from gpiozero import Button; button = Button(17); print('Button working')"
```

### Camera not found
```bash
# Check camera connections
rpicam-still --camera 1 -o test1.jpg
rpicam-still -o test2.jpg
```

### DepthAI not connected
```bash
# Test DepthAI connection
python3 -c "import depthai as dai; print('DepthAI available')"
```

## Dependencies

- `opencv-python` - Video processing
- `depthai` - DepthAI camera interface
- `gpiozero` - GPIO control
- `numpy` - Numerical processing 