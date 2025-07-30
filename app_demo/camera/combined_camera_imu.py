#!/usr/bin/env python3
import cv2
import depthai as dai
import time
import sys
import os
import datetime
import json

def start_recording(filename):
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
    camRgb.setPreviewSize(1920, 1080)
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
            
            # Create output directory
            output_directory = "/home/sagiv/sogofw/app_demo/recordings"
            os.makedirs(output_directory, exist_ok=True)
            
            # Create video writer
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            output_filename = f"{filename}_{timestamp}.avi"
            output_file = os.path.join(output_directory, output_filename)
            
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            out = cv2.VideoWriter(output_file, fourcc, 20.0, (1920, 1080))
            
            if not out.isOpened():
                print("Error: Could not initialize video writer")
                return False
            
            print(f"Recording started: {output_file}")
            
            while True:
                inRgb = qRgb.tryGet()
                inImu = qImu.tryGet()
                
                if inRgb is not None:
                    frame = inRgb.getCvFrame()
                    
                    # Add timestamp
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                    
                    # Write frame
                    out.write(frame)
                
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
                    
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    out.release()
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 combined_camera_imu.py <filename> [--action start]")
        return
    
    filename = sys.argv[1]
    action = "start"
    
    if len(sys.argv) > 2 and sys.argv[2] == "--action":
        if len(sys.argv) > 3:
            action = sys.argv[3]
    
    if action == "start":
        start_recording(filename)
    else:
        print("Unknown action")

if __name__ == "__main__":
    main() 