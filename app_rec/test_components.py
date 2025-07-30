#!/usr/bin/env python3
"""
Test script to verify all components work individually
"""

import subprocess
import sys
import time

def test_button():
    """Test GPIO button"""
    print("Testing GPIO button...")
    try:
        from gpiozero import Button, LED
        button = Button(17, pull_up=True)
        led = LED(27)
        print("✅ GPIO components imported successfully")
        print("Press button to test LED (Ctrl+C to exit)")
        
        # Simple test - turn LED on/off with button
        button.when_pressed = led.on
        button.when_released = led.off
        
        while True:
            time.sleep(0.1)
            
    except ImportError as e:
        print(f"❌ GPIO test failed: {e}")
        return False
    except KeyboardInterrupt:
        print("\nButton test completed")
        return True

def test_cameras():
    """Test RPi cameras"""
    print("\nTesting RPi cameras...")
    
    # Test camera 1
    try:
        result = subprocess.run([
            "rpicam-still", "--camera", "1", "-o", "test_camera1.jpg", "--timeout", "1000"
        ], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Camera 1 working")
        else:
            print(f"❌ Camera 1 failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Camera 1 test failed: {e}")
    
    # Test camera 2
    try:
        result = subprocess.run([
            "rpicam-still", "-o", "test_camera2.jpg", "--timeout", "1000"
        ], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Camera 2 working")
        else:
            print(f"❌ Camera 2 failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Camera 2 test failed: {e}")

def test_depthai():
    """Test DepthAI camera and IMU"""
    print("\nTesting DepthAI camera and IMU...")
    try:
        import depthai as dai
        import cv2
        
        # Create simple pipeline
        pipeline = dai.Pipeline()
        camRgb = pipeline.create(dai.node.ColorCamera)
        xlinkOut = pipeline.create(dai.node.XLinkOut)
        xlinkOut.setStreamName("rgb")
        
        camRgb.setPreviewSize(300, 300)
        camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
        camRgb.preview.link(xlinkOut.input)
        
        with dai.Device(pipeline) as device:
            print("✅ DepthAI device connected successfully!")
            
            # Test for a few frames
            qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            
            for i in range(10):
                inRgb = qRgb.tryGet()
                if inRgb is not None:
                    frame = inRgb.getCvFrame()
                    print(f"✅ Frame {i+1} received: {frame.shape}")
                    break
                time.sleep(0.1)
            else:
                print("❌ No frames received from DepthAI")
                
    except ImportError as e:
        print(f"❌ DepthAI import failed: {e}")
    except Exception as e:
        print(f"❌ DepthAI test failed: {e}")

def test_imu():
    """Test IMU data collection"""
    print("\nTesting IMU data collection...")
    try:
        import depthai as dai
        
        # Create IMU pipeline
        pipeline = dai.Pipeline()
        imu = pipeline.create(dai.node.IMU)
        xlinkOut = pipeline.create(dai.node.XLinkOut)
        xlinkOut.setStreamName("imu")
        
        imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 500)
        imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)
        imu.enableIMUSensor(dai.IMUSensor.ROTATION_VECTOR, 400)
        imu.setBatchReportThreshold(1)
        imu.setMaxBatchReports(10)
        
        imu.out.link(xlinkOut.input)
        
        with dai.Device(pipeline) as device:
            print("✅ IMU device connected successfully!")
            
            # Test for IMU data
            qImu = device.getOutputQueue(name="imu", maxSize=50, blocking=False)
            
            for i in range(10):
                inImu = qImu.tryGet()
                if inImu is not None:
                    imuPackets = inImu.packets
                    for imuPacket in imuPackets:
                        if hasattr(imuPacket, 'acceleroMeter'):
                            print("✅ Accelerometer data received")
                        if hasattr(imuPacket, 'gyroscope'):
                            print("✅ Gyroscope data received")
                        if hasattr(imuPacket, 'rotationVector'):
                            print("✅ Rotation vector data received")
                        break
                    break
                time.sleep(0.1)
            else:
                print("❌ No IMU data received")
                
    except Exception as e:
        print(f"❌ IMU test failed: {e}")

def main():
    """Run all tests"""
    print("=== Component Test Suite ===")
    
    # Test each component
    test_button()
    test_cameras()
    test_depthai()
    test_imu()
    
    print("\n=== Test Summary ===")
    print("Check the output above for ✅ (success) or ❌ (failure) indicators")
    print("All components should show ✅ for a successful setup")

if __name__ == "__main__":
    main() 