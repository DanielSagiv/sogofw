#!/usr/bin/env python3

import cv2
import depthai as dai
import time
import math
import json
import sys

def test_camera_imu():
    """Test function to verify camera IMU functionality"""
    
    # Check if device is available
    try:
        device = dai.Device()
        imuType = device.getConnectedIMU()
        imuFirmwareVersion = device.getIMUFirmwareVersion()
        print(f"IMU type: {imuType}, firmware version: {imuFirmwareVersion}")
        
        if imuType == "BNO086":
            print("Rotation vector output is supported!")
        else:
            print("Rotation vector output is NOT supported by this IMU")
            
    except Exception as e:
        print(f"Error connecting to device: {e}")
        return False
    
    # Create pipeline
    pipeline = dai.Pipeline()

    # Define sources and outputs
    imu = pipeline.create(dai.node.IMU)
    xlinkOut = pipeline.create(dai.node.XLinkOut)

    xlinkOut.setStreamName("imu")

    # Enable IMU sensors
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 500)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)
    imu.enableIMUSensor(dai.IMUSensor.ROTATION_VECTOR, 400)

    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(10)

    # Link plugins IMU -> XLINK
    imu.out.link(xlinkOut.input)

    # Pipeline is defined, now we can connect to the device
    with dai.Device(pipeline) as device:
        def timeDeltaToMilliS(delta) -> float:
            return delta.total_seconds()*1000

        # Output queue for imu bulk packets
        imuQueue = device.getOutputQueue(name="imu", maxSize=50, blocking=False)
        baseTs = None
        sample_count = 0
        
        print("Starting IMU data collection...")
        print("Press Ctrl+C to stop")
        
        while True:
            try:
                imuData = imuQueue.get()  # blocking call

                imuPackets = imuData.packets
                for imuPacket in imuPackets:
                    data = {}
                    
                    # Get accelerometer data
                    if hasattr(imuPacket, 'acceleroMeter'):
                        acceleroValues = imuPacket.acceleroMeter
                        acceleroTs = acceleroValues.getTimestampDevice()
                        if baseTs is None:
                            baseTs = acceleroTs
                        acceleroTs = timeDeltaToMilliS(acceleroTs - baseTs)
                        
                        data['accel'] = {
                            'x': acceleroValues.x,
                            'y': acceleroValues.y,
                            'z': acceleroValues.z,
                            'timestamp': acceleroTs
                        }
                    
                    # Get gyroscope data
                    if hasattr(imuPacket, 'gyroscope'):
                        gyroValues = imuPacket.gyroscope
                        gyroTs = gyroValues.getTimestampDevice()
                        if baseTs is None:
                            baseTs = gyroTs
                        gyroTs = timeDeltaToMilliS(gyroTs - baseTs)
                        
                        data['gyro'] = {
                            'x': gyroValues.x,
                            'y': gyroValues.y,
                            'z': gyroValues.z,
                            'timestamp': gyroTs
                        }
                    
                    # Get rotation vector data
                    if hasattr(imuPacket, 'rotationVector'):
                        rVvalues = imuPacket.rotationVector
                        rvTs = rVvalues.getTimestampDevice()
                        if baseTs is None:
                            baseTs = rvTs
                        rvTs = timeDeltaToMilliS(rvTs - baseTs)
                        
                        data['rotation_vector'] = {
                            'i': rVvalues.i,
                            'j': rVvalues.j,
                            'k': rVvalues.k,
                            'real': rVvalues.real,
                            'accuracy': rVvalues.rotationVectorAccuracy,
                            'timestamp': rvTs
                        }
                    
                    # Output data
                    if data:
                        sample_count += 1
                        if sample_count <= 10:  # Show first 10 samples
                            print(f"Sample {sample_count}: {json.dumps(data, indent=2)}")
                        elif sample_count == 11:
                            print("... (continuing data collection)")
                        
                        # Output JSON for C program consumption
                        print(json.dumps(data))
                        sys.stdout.flush()
                        
            except KeyboardInterrupt:
                print("\nStopping IMU data collection...")
                break
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                break

if __name__ == "__main__":
    test_camera_imu() 