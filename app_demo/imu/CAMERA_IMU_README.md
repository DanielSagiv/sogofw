# Camera IMU Integration

This document explains the changes made to integrate IMU data from a camera device instead of using a separate BNO055 sensor.

## Overview

The project has been updated to use the integrated IMU from a DepthAI camera (likely containing a BNO086 sensor) instead of the external BNO055 sensor. This provides several advantages:

- **Simplified Hardware**: No need for separate IMU sensor
- **Synchronized Data**: IMU data is naturally synchronized with camera data
- **Reduced Complexity**: Fewer components and connections
- **Better Integration**: IMU data comes from the same device as video

## Changes Made

### 1. New Files Created

- `camera_imu.h` - Header file for camera IMU interface
- `camera_imu.c` - Implementation of camera IMU functionality
- `test_camera_imu.py` - Standalone Python test script

### 2. Files Modified

- `app_main.c` - Updated to use `camera_imu_start()` and `camera_imu_get_data()`
- `Makefile` - Updated to compile `camera_imu.o` instead of BNO055 files

### 3. Files Removed (No Longer Used)

- `bno055.h` - BNO055 sensor header
- `bno055.c` - BNO055 sensor implementation
- `bno055_api.h` - BNO055 API header
- `bno055_api.c` - BNO055 API implementation

## How It Works

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DepthAI       │    │   Python        │    │   C Application │
│   Camera        │───▶│   IMU Script    │───▶│   camera_imu.c  │
│   (BNO086)      │    │   (JSON output) │    │   (JSON parser) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

1. **Camera IMU**: DepthAI camera with integrated BNO086 sensor
2. **Python Script**: Collects IMU data and outputs JSON format
3. **C Interface**: Parses JSON and provides data to main application
4. **Main App**: Uses IMU data for recording and analysis

### IMU Data Types

The camera IMU provides three types of data:

1. **Accelerometer**: Raw acceleration in m/s²
2. **Gyroscope**: Angular velocity in rad/s
3. **Rotation Vector**: Quaternion orientation data

## API Functions

### Initialization
```c
int camera_imu_start(void);  // Start IMU data collection
void camera_imu_stop(void);  // Stop IMU data collection
```

### Data Retrieval
```c
int camera_imu_get_data(char *buf, int len);  // Get formatted data
int camera_imu_get_accel(imu_accel_t *accel); // Get accelerometer data
int camera_imu_get_gyro(imu_gyro_t *gyro);    // Get gyroscope data
int camera_imu_get_rotation_vector(imu_rotation_vector_t *rv); // Get rotation vector
```

## Data Format

The IMU data is formatted as CSV for compatibility with the existing system:

```
accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z,rv_i,rv_j,rv_k
```

## Requirements

### Hardware
- DepthAI camera with integrated IMU (BNO086 recommended)
- USB connection to host system

### Software Dependencies
```bash
# Python dependencies
pip install depthai opencv-python

# System dependencies
sudo apt install python3-pip
```

## Testing

### 1. Test Camera IMU Independently
```bash
cd app_demo/imu
python3 test_camera_imu.py
```

### 2. Test Full Application
```bash
cd app_demo
make clean
make all
./app_demo
```

## Troubleshooting

### Common Issues

1. **No IMU Data**: Check if camera is connected and recognized
2. **Python Errors**: Ensure depthai library is installed
3. **Permission Issues**: Run with appropriate USB permissions
4. **JSON Parse Errors**: Check Python script output format

### Debug Commands

```bash
# Check if camera is detected
lsusb | grep DepthAI

# Test Python script directly
python3 -c "import depthai as dai; print('DepthAI available')"

# Check IMU type
python3 test_camera_imu.py | head -5
```

## Migration Notes

### From BNO055 to Camera IMU

1. **Hardware**: Remove BNO055 sensor and I2C connections
2. **Software**: Replace BNO055 API calls with camera IMU calls
3. **Data Format**: Output format remains the same for compatibility
4. **Timing**: IMU data is now synchronized with camera data

### Compatibility

The new implementation maintains compatibility with existing data processing:
- Same CSV output format
- Same data collection frequency
- Same file naming convention
- Same recording triggers

## Performance Considerations

- **Latency**: Python script adds some latency (~10-50ms)
- **CPU Usage**: Additional Python process running
- **Memory**: JSON parsing overhead
- **Reliability**: More complex data path but better integration

## Future Improvements

1. **Direct C Integration**: Replace Python script with direct C DepthAI API
2. **Better Error Handling**: More robust error detection and recovery
3. **Configuration**: Make IMU rates configurable
4. **Optimization**: Reduce JSON parsing overhead 