#!/usr/bin/env python3
"""
Multi-Camera Recording System with IMU Data Collection (gpiod version)
Integrates: Button control, 3 cameras (2 RPi cameras + 1 DepthAI), IMU data
Uses gpiod library for Raspberry Pi 5 compatibility
"""

import cv2
import depthai as dai
import time
import json
import os
import datetime
import threading
import subprocess
import signal
import sys
import gpiod
from pathlib import Path

class MultiCameraRecorder:
    def __init__(self):
        self.recording = False
        self.recording_threads = []
        self.stop_recording_event = threading.Event()
        
        # GPIO setup
        self.BUTTON_PIN = 17
        self.LED_PIN = 27
        
        # GPIO objects
        self.chip = None
        self.button_line = None
        self.led_line = None
        
        # Setup GPIO using gpiod
        self.setup_gpio()
        
        # Recording paths
        self.recordings_dir = Path("recordings")
        self.recordings_dir.mkdir(exist_ok=True)
        
        # Camera processes
        self.camera1_process = None
        self.camera2_process = None
        self.depthai_device = None
        
        # File handles
        self.imu_file = None
        self.gyro_file = None
        self.camera1_file = None
        self.camera2_file = None
        self.camera3_file = None
        
        # Button state tracking
        self.last_button_state = 1  # 1 = not pressed (pull-up)
        self.button_pressed = False
        
        print("Multi-Camera Recording System Initialized")
        print("Press button to start/stop recording")
    
    def setup_gpio(self):
        """Setup GPIO with proper error handling"""
        try:
            # Clean up any existing GPIO usage
            self.cleanup_gpio()
            
            # Setup GPIO using gpiod
            self.chip = gpiod.Chip('gpiochip0')
            self.button_line = self.chip.get_line(self.BUTTON_PIN)
            self.led_line = self.chip.get_line(self.LED_PIN)
            
            # Configure button as input with pull-up
            self.button_line.request(consumer="button", type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
            
            # Configure LED as output
            self.led_line.request(consumer="led", type=gpiod.LINE_REQ_DIR_OUT)
            self.led_line.set_value(0)  # LED off initially
            
            print("✅ GPIO setup successful using gpiod")
            
        except Exception as e:
            print(f"❌ GPIO setup failed: {e}")
            print("Trying alternative GPIO setup...")
            self.setup_gpio_alternative()
    
    def cleanup_gpio(self):
        """Clean up GPIO resources"""
        try:
            if self.chip:
                self.chip.close()
                self.chip = None
                self.button_line = None
                self.led_line = None
        except:
            pass
        
        # Also try to release GPIO pins via system
        try:
            os.system(f"echo {self.BUTTON_PIN} > /sys/class/gpio/unexport 2>/dev/null")
            os.system(f"echo {self.LED_PIN} > /sys/class/gpio/unexport 2>/dev/null")
        except:
            pass
    
    def setup_gpio_alternative(self):
        """Alternative GPIO setup using system commands"""
        try:
            # Clean up first
            os.system(f"echo {self.BUTTON_PIN} > /sys/class/gpio/unexport 2>/dev/null")
            os.system(f"echo {self.LED_PIN} > /sys/class/gpio/unexport 2>/dev/null")
            time.sleep(0.1)
            
            # Export GPIO pins
            os.system(f"echo {self.BUTTON_PIN} > /sys/class/gpio/export")
            os.system(f"echo {self.LED_PIN} > /sys/class/gpio/export")
            
            # Set directions
            os.system(f"echo in > /sys/class/gpio/gpio{self.BUTTON_PIN}/direction")
            os.system(f"echo out > /sys/class/gpio/gpio{self.LED_PIN}/direction")
            
            # Set pull-up for button
            os.system(f"echo pullup > /sys/class/gpio/gpio{self.BUTTON_PIN}/direction")
            
            print("✅ Alternative GPIO setup successful")
            
        except Exception as e:
            print(f"❌ Alternative GPIO setup failed: {e}")
            print("Continuing without GPIO...")
    
    def read_button_gpiod(self):
        """Read button state using gpiod"""
        try:
            if self.button_line:
                return self.button_line.get_value()
            else:
                return 1  # Default to not pressed
        except:
            return 1  # Default to not pressed
    
    def read_button_alternative(self):
        """Read button state using system files"""
        try:
            with open(f"/sys/class/gpio/gpio{self.BUTTON_PIN}/value", "r") as f:
                return int(f.read().strip())
        except:
            return 1  # Default to not pressed
    
    def set_led_gpiod(self, state):
        """Set LED state using gpiod"""
        try:
            if self.led_line:
                self.led_line.set_value(1 if state else 0)
        except:
            pass
    
    def set_led_alternative(self, state):
        """Set LED state using system files"""
        try:
            with open(f"/sys/class/gpio/gpio{self.LED_PIN}/value", "w") as f:
                f.write("1" if state else "0")
        except:
            pass
    
    def check_button(self):
        """Check button state and handle press"""
        try:
            # Try gpiod first
            current_state = self.read_button_gpiod()
        except:
            # Fallback to system files
            current_state = self.read_button_alternative()
        
        # Button is pressed when state is 0 (due to pull-up)
        if current_state == 0 and self.last_button_state == 1:
            # Button just pressed
            self.button_pressed = True
            print("Button pressed!")
            
            # Toggle recording
            if not self.recording:
                self.start_recording()
            else:
                self.stop_recording()
        
        self.last_button_state = current_state
        return self.button_pressed
    
    def get_timestamp(self):
        """Get current timestamp for filenames"""
        return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def start_recording(self):
        """Start recording all cameras and IMU data"""
        if self.recording:
            print("Already recording!")
            return
            
        print("Starting recording...")
        self.recording = True
        
        # Turn on LED
        try:
            self.set_led_gpiod(True)
        except:
            self.set_led_alternative(True)
        
        # Get timestamp for this recording session
        timestamp = self.get_timestamp()
        
        # Start camera 1 (RPi camera 1)
        self.start_camera1_recording(timestamp)
        
        # Start camera 2 (RPi camera 2) 
        self.start_camera2_recording(timestamp)
        
        # Start camera 3 (DepthAI) and IMU
        self.start_depthai_recording(timestamp)
        
        print(f"Recording started - Session: {timestamp}")
    
    def stop_recording(self):
        """Stop all recording"""
        if not self.recording:
            print("Not recording!")
            return
            
        print("Stopping recording...")
        self.recording = False
        
        # Turn off LED
        try:
            self.set_led_gpiod(False)
        except:
            self.set_led_alternative(False)
        
        # Stop camera processes
        self.stop_camera_processes()
        
        # Stop DepthAI recording
        self.stop_depthai_recording()
        
        print("Recording stopped")
    
    def start_camera1_recording(self, timestamp):
        """Start RPi camera 1 recording"""
        filename = f"camera1_{timestamp}.h264"
        filepath = self.recordings_dir / filename
        
        # Try a much simpler command to test if camera works
        cmd = f"rpicam-vid --camera 1 --output {filepath}"
        
        try:
            print(f"Starting Camera 1 with command: {cmd}")
            print(f"Output file: {filepath}")
            
            # Start the process
            self.camera1_process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            # Check if process started successfully
            if self.camera1_process.poll() is None:
                print(f"Camera 1 recording started successfully: {filename}")
            else:
                stdout, stderr = self.camera1_process.communicate()
                print(f"Camera 1 failed to start. stdout: {stdout.decode()}")
                print(f"Camera 1 failed to start. stderr: {stderr.decode()}")
                
        except Exception as e:
            print(f"Error starting camera 1: {e}")
    
    def start_camera2_recording(self, timestamp):
        """Start RPi camera 2 recording"""
        filename = f"camera2_{timestamp}.h264"
        filepath = self.recordings_dir / filename
        
        # Try a much simpler command to test if camera works
        cmd = f"rpicam-vid --output {filepath}"
        
        try:
            print(f"Starting Camera 2 with command: {cmd}")
            print(f"Output file: {filepath}")
            
            # Start the process
            self.camera2_process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            # Check if process started successfully
            if self.camera2_process.poll() is None:
                print(f"Camera 2 recording started successfully: {filename}")
            else:
                stdout, stderr = self.camera2_process.communicate()
                print(f"Camera 2 failed to start. stdout: {stdout.decode()}")
                print(f"Camera 2 failed to start. stderr: {stderr.decode()}")
                
        except Exception as e:
            print(f"Error starting camera 2: {e}")
    
    def start_depthai_recording(self, timestamp):
        """Start DepthAI camera and IMU recording"""
        # Create IMU and gyro files
        imu_filename = f"imu_vector_{timestamp}.json"
        gyro_filename = f"gyroscope_{timestamp}.json"
        
        self.imu_file = open(self.recordings_dir / imu_filename, 'w')
        self.gyro_file = open(self.recordings_dir / gyro_filename, 'w')
        
        # Start DepthAI recording thread
        self.depthai_thread = threading.Thread(
            target=self.depthai_recording_thread,
            args=(timestamp,)
        )
        self.depthai_thread.daemon = True
        self.depthai_thread.start()
        
        print(f"DepthAI recording started: {timestamp}")
    
    def depthai_recording_thread(self, timestamp):
        """Thread for DepthAI camera and IMU recording"""
        try:
            # Create pipeline
            pipeline = dai.Pipeline()
            
            # Define sources and outputs
            camRgb = pipeline.create(dai.node.ColorCamera)
            imu = pipeline.create(dai.node.IMU)
            xlinkOut = pipeline.create(dai.node.XLinkOut)
            imuXlinkOut = pipeline.create(dai.node.XLinkOut)
            
            xlinkOut.setStreamName("rgb")
            imuXlinkOut.setStreamName("imu")
            
            # Camera properties
            camRgb.setPreviewSize(1920, 1080)
            camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
            camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
            camRgb.setInterleaved(False)
            camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
            
            # IMU properties
            imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 500)
            imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)
            imu.enableIMUSensor(dai.IMUSensor.ROTATION_VECTOR, 400)
            imu.setBatchReportThreshold(1)
            imu.setMaxBatchReports(10)
            
            # Linking
            camRgb.preview.link(xlinkOut.input)
            imu.out.link(imuXlinkOut.input)
            
            # Connect to device
            with dai.Device(pipeline) as device:
                print("DepthAI device connected successfully!")
                
                # Output queues
                qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
                qImu = device.getOutputQueue(name="imu", maxSize=50, blocking=False)
                
                # Create video writer
                video_filename = f"camera3_{timestamp}.avi"
                video_filepath = self.recordings_dir / video_filename
                
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                out = cv2.VideoWriter(str(video_filepath), fourcc, 20.0, (1920, 1080))
                
                if not out.isOpened():
                    print("Error: Could not initialize video writer")
                    return
                
                print(f"DepthAI video recording: {video_filename}")
                
                while not self.stop_recording_event.is_set():
                    inRgb = qRgb.tryGet()
                    inImu = qImu.tryGet()
                    
                    if inRgb is not None:
                        frame = inRgb.getCvFrame()
                        
                        # Add timestamp
                        timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        cv2.putText(frame, timestamp_str, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                        
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
                                gyro_data = {
                                    'x': gyroValues.x,
                                    'y': gyroValues.y,
                                    'z': gyroValues.z,
                                    'timestamp': time.time()
                                }
                                # Write gyroscope data
                                self.gyro_file.write(json.dumps(gyro_data) + '\n')
                                self.gyro_file.flush()
                            
                            # Get rotation vector data
                            if hasattr(imuPacket, 'rotationVector'):
                                rvValues = imuPacket.rotationVector
                                rv_data = {
                                    'i': rvValues.i,
                                    'j': rvValues.j,
                                    'k': rvValues.k,
                                    'real': rvValues.real,
                                    'accuracy': float(rvValues.accuracy),
                                    'timestamp': time.time()
                                }
                                # Write rotation vector data
                                self.imu_file.write(json.dumps(rv_data) + '\n')
                                self.imu_file.flush()
                
                # Cleanup
                out.release()
                
        except Exception as e:
            print(f"Error in DepthAI recording thread: {e}")
    
    def stop_camera_processes(self):
        """Stop RPi camera recording processes"""
        if self.camera1_process:
            self.camera1_process.terminate()
            self.camera1_process.wait()
            self.camera1_process = None
            print("Camera 1 stopped")
        
        if self.camera2_process:
            self.camera2_process.terminate()
            self.camera2_process.wait()
            self.camera2_process = None
            print("Camera 2 stopped")
    
    def stop_depthai_recording(self):
        """Stop DepthAI recording"""
        self.stop_recording_event.set()
        
        if self.depthai_thread:
            self.depthai_thread.join(timeout=5)
        
        if self.imu_file:
            self.imu_file.close()
            self.imu_file = None
        
        if self.gyro_file:
            self.gyro_file.close()
            self.gyro_file = None
        
        print("DepthAI recording stopped")
    
    def cleanup(self):
        """Cleanup resources"""
        if self.recording:
            self.stop_recording()
        
        # Turn off LED
        try:
            self.set_led_gpiod(False)
        except:
            self.set_led_alternative(False)
        
        # Cleanup gpiod
        self.cleanup_gpio()
        
        print("Cleanup completed")
    
    def run(self):
        """Main run loop"""
        try:
            print("Multi-Camera Recording System Ready")
            print("Press button to start/stop recording")
            print("Press Ctrl+C to exit")
            
            # Keep the main thread alive and check button
            while True:
                self.check_button()
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.cleanup()
            sys.exit(0)

def main():
    """Main entry point"""
    recorder = MultiCameraRecorder()
    recorder.run()

if __name__ == "__main__":
    main() 
    #
    #