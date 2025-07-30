#!/usr/bin/env python3
import depthai as dai
import time
import json
import sys

def test_camera_imu_headless():
    print("Testing camera and IMU functionality (headless mode)...")
    
    # Create pipeline
    pipeline = dai.Pipeline()
    
    # Define sources and outputs
    camRgb = pipeline.create(dai.node.ColorCamera)
    imu = pipeline.create(dai.node.IMU)
    xlinkOut = pipeline.create(dai.node.XLinkOut)
    imuXlinkOut = pipeline.create(dai.node.XLinkOut)
    
    xlinkOut.setStreamName("rgb")
    imuXlinkOut.setStreamName("imu")
    
    # Properties
    camRgb.setPreviewSize(300, 300)
    camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    camRgb.setInterleaved(False)
    camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    
    # Enable IMU sensors
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 500)
    imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)
    imu.enableIMUSensor(dai.IMUSensor.ROTATION_VECTOR, 400)
    
    imu.setBatchReportThreshold(1)
    imu.setMaxBatchReports(10)
    
    # Linking
    camRgb.preview.link(xlinkOut.input)
    imu.out.link(imuXlinkOut.input)
    
    # Connect to device
    try:
        with dai.Device(pipeline) as device:
            print("Device connected successfully!")
            
            # Output queues
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            qImu = device.getOutputQueue(name="imu", maxSize=50, blocking=False)
            
            # Time tracking
            startTime = time.monotonic()
            counter = 0
            fps = 0
            
            print("Starting data collection (press Ctrl+C to stop)...")
            
            while True:
                inRgb = qRgb.tryGet()
                inImu = qImu.tryGet()
                
                if inRgb is not None:
                    frame = inRgb.getCvFrame()
                    counter += 1
                    current_time = time.monotonic()
                    if (current_time - startTime) > 1:
                        fps = counter / (current_time - startTime)
                        print(f"Camera FPS: {fps:.2f}")
                        counter = 0
                        startTime = current_time
                
                if inImu is not None:
                    imuPackets = inImu.packets
                    for imuPacket in imuPackets:
                        data = {}
                        
                        # Get accelerometer data
                        if hasattr(imuPacket, 'acceleroMeter'):
                            acceleroValues = imuPacket.acceleroMeter
                            data['accel'] = {
                                'x': acceleroValues.x,
                                'y': acceleroValues.y,
                                'z': acceleroValues.z,
                                'timestamp': time.time()
                            }
                        
                        # Get gyroscope data
                        if hasattr(imuPacket, 'gyroscope'):
                            gyroValues = imuPacket.gyroscope
                            data['gyro'] = {
                                'x': gyroValues.x,
                                'y': gyroValues.y,
                                'z': gyroValues.z,
                                'timestamp': time.time()
                            }
                        
                        # Get rotation vector data
                        if hasattr(imuPacket, 'rotationVector'):
                            rvValues = imuPacket.rotationVector
                            data['rotation_vector'] = {
                                'i': rvValues.i,
                                'j': rvValues.j,
                                'k': rvValues.k,
                                'real': rvValues.real,
                                'accuracy': float(rvValues.accuracy),
                                'timestamp': time.time()
                            }
                        
                        if data:
                            print(json.dumps(data))
                    
    except KeyboardInterrupt:
        print("\nTest stopped by user")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_camera_imu_headless() 