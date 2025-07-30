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

3. **Test GPIO:**
   ```bash
   python test_gpiod.py
   ```

## Usage

1. **Run the application (try in this order):**
   ```bash
   # Try gpiod version first (recommended for Pi 5)
   python main_gpiod.py
   
   # If that fails, try alternative version
   python main_alternative.py
   
   # Last resort - original version
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
├── main_gpiod.py        # Main app (gpiod - Pi 5 compatible)
├── main_alternative.py  # Alternative (RPi.GPIO)
├── main.py              # Original (gpiozero)
├── requirements.txt      # Python dependencies
├── setup.sh            # Setup script
├── README.md           # This file
├── test_gpiod.py       # gpiod test script
├── test_gpio.py        # RPi.GPIO test script
├── test_components.py  # Component testing script
├── venv/               # Virtual environment
└── recordings/         # Output files directory
```

## GPIO Troubleshooting

### If you get "Cannot determine SOC peripheral base address" error:

1. **Try the gpiod version (recommended for Pi 5):**
   ```bash
   python main_gpiod.py
   ```

2. **Test gpiod manually:**
   ```bash
   python test_gpiod.py
   ```

3. **If gpiod fails, try alternative:**
   ```bash
   python main_alternative.py
   ```

4. **Run as root (if needed):**
   ```bash
   sudo python main_gpiod.py
   ```

5. **Check GPIO permissions:**
   ```bash
   groups $USER
   ls -la /dev/gpiomem
   ```

6. **Reinstall GPIO libraries:**
   ```bash
   pip install --upgrade gpiod RPi.GPIO gpiozero
   ```

### Button not working
```bash
# Test button outside virtual environment
python3 -c "import gpiod; chip = gpiod.Chip('gpiochip0'); line = chip.get_line(17); line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN); print('Button pin:', line.get_value())"
```

## Advantages over C Version

- ✅ **Simpler GPIO handling** - `gpiod` library for Pi 5
- ✅ **Better camera integration** - Direct DepthAI Python API
- ✅ **Easier IMU handling** - Native Python JSON processing
- ✅ **No compilation issues** - Pure Python
- ✅ **Faster development** - No C compilation cycles
- ✅ **Better error handling** - Python exceptions
- ✅ **Easier to modify** - More readable and maintainable

## Troubleshooting

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
- `gpiod` - GPIO control (Pi 5 compatible)
- `gpiozero` - GPIO control (main version)
- `RPi.GPIO` - GPIO control (alternative version)
- `numpy` - Numerical processing 