#!/usr/bin/env python3
"""
Multi-Camera Recording System with IMU Data Collection and Skeleton Recognition (No GPIO version)
Integrates: 3 cameras (2 RPi cameras + 1 DepthAI), IMU data, Grove LCD RGB, Skeleton Recognition
No GPIO - for testing camera and IMU functionality
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
import serial
from pathlib import Path
from grove_lcd_rgb import set_text, set_rgb

# MediaPipe imports for skeleton recognition
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions

# Suppress TensorFlow warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

class MultiCameraRecorder:
    def __init__(self):
        self.recording = False
        self.recording_threads = []
        self.stop_recording_event = threading.Event()
        
        # Recording paths
        self.recordings_dir = Path("recordings")
        self.recordings_dir.mkdir(exist_ok=True)
        
        # Camera processes
        self.camera1_process = None
        self.camera2_process = None
        self.depthai_device = None
        
        # Thread handles
        self.depthai_thread = None
        self.gps_thread = None
        
        # File handles
        self.imu_file = None
        self.gyro_file = None
        self.skeleton_file = None
        self.gps_file = None
        self.camera1_file = None
        self.camera2_file = None
        self.camera3_file = None
        
        # Skeleton recognition
        self.pose_detector = None
        self.skeleton_enabled = True  # Toggle for skeleton detection
        
        # Initialize skeleton recognition
        self.initialize_pose_detector()
        
        # Initialize LCD
        try:
            set_rgb(0, 128, 64)  # Green color
            set_text("SOGO READY")
            print("LCD initialized successfully")
        except Exception as e:
            print(f"LCD initialization failed: {e}")
        
        print("Multi-Camera Recording System Initialized (No GPIO)")
        print("Press Enter to start/stop recording")
        print("Press Ctrl+C to exit")
    
    def get_timestamp(self):
        """Get current timestamp for filenames"""
        return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def initialize_pose_detector(self):
        """Initialize MediaPipe pose detector"""
        try:
            # Use lite model for better performance
            model_path = Path(__file__).parent / "models" / "pose_landmarker_lite.task"
            if not model_path.exists():
                print(f"Warning: Skeleton model not found at {model_path}")
                self.skeleton_enabled = False
                return
            
            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                output_segmentation_masks=False  # Disable for better performance
            )
            self.pose_detector = vision.PoseLandmarker.create_from_options(options)
            print("Skeleton recognition initialized successfully")
            
        except Exception as e:
            print(f"Error initializing skeleton recognition: {e}")
            self.skeleton_enabled = False
    
    def draw_landmarks_on_frame(self, frame, detection_result):
        """Draw skeleton landmarks on frame"""
        if not self.skeleton_enabled or not detection_result.pose_landmarks:
            return frame
        
        annotated_frame = frame.copy()
        
        for pose_landmarks in detection_result.pose_landmarks:
            pose_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            pose_landmarks_proto.landmark.extend(
                [landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) 
                 for landmark in pose_landmarks]
            )
            solutions.drawing_utils.draw_landmarks(
                annotated_frame,
                pose_landmarks_proto,
                solutions.pose.POSE_CONNECTIONS,
                solutions.drawing_styles.get_default_pose_landmarks_style()
            )
        
        return annotated_frame
    
    def process_skeleton_data(self, detection_result, timestamp):
        """Process and save skeleton data"""
        if not self.skeleton_enabled or not detection_result.pose_landmarks:
            return
        
        try:
            for pose_landmarks in detection_result.pose_landmarks:
                landmarks_data = {
                    'timestamp': timestamp,
                    'landmarks': []
                }
                
                for i, landmark in enumerate(pose_landmarks):
                    landmark_data = {
                        'id': i,
                        'x': landmark.x,
                        'y': landmark.y,
                        'z': landmark.z,
                        'visibility': getattr(landmark, 'visibility', 0.0)
                    }
                    landmarks_data['landmarks'].append(landmark_data)
                
                # Save to skeleton file
                if self.skeleton_file:
                    self.skeleton_file.write(json.dumps(landmarks_data) + '\n')
                    self.skeleton_file.flush()
                    
        except Exception as e:
            print(f"Error processing skeleton data: {e}")
    
    def parse_gps_data(self, gps_line):
        """Parse GPS NMEA data and extract useful information"""
        try:
            if gps_line.startswith('$GPGGA'):
                # Parse GGA sentence (Global Positioning System Fix Data)
                parts = gps_line.split(',')
                if len(parts) >= 15:
                    gps_data = {
                        'timestamp': time.time(),
                        'type': 'GGA',
                        'time': parts[1] if parts[1] else None,
                        'latitude': parts[2] if parts[2] else None,
                        'latitude_dir': parts[3] if parts[3] else None,
                        'longitude': parts[4] if parts[4] else None,
                        'longitude_dir': parts[5] if parts[5] else None,
                        'quality': parts[6] if parts[6] else None,
                        'satellites': parts[7] if parts[7] else None,
                        'hdop': parts[8] if parts[8] else None,
                        'altitude': parts[9] if parts[9] else None,
                        'altitude_unit': parts[10] if parts[10] else None,
                        'geoid_height': parts[11] if parts[11] else None,
                        'geoid_height_unit': parts[12] if parts[12] else None,
                        'dgps_age': parts[13] if parts[13] else None,
                        'checksum': parts[14].split('*')[1] if '*' in parts[14] else None
                    }
                    return gps_data
            
            elif gps_line.startswith('$GPRMC'):
                # Parse RMC sentence (Recommended Minimum sentence C)
                parts = gps_line.split(',')
                if len(parts) >= 12:
                    gps_data = {
                        'timestamp': time.time(),
                        'type': 'RMC',
                        'time': parts[1] if parts[1] else None,
                        'status': parts[2] if parts[2] else None,
                        'latitude': parts[3] if parts[3] else None,
                        'latitude_dir': parts[4] if parts[4] else None,
                        'longitude': parts[5] if parts[5] else None,
                        'longitude_dir': parts[6] if parts[6] else None,
                        'speed': parts[7] if parts[7] else None,
                        'course': parts[8] if parts[8] else None,
                        'date': parts[9] if parts[9] else None,
                        'variation': parts[10] if parts[10] else None,
                        'variation_dir': parts[11] if parts[11] else None,
                        'checksum': parts[12].split('*')[1] if '*' in parts[12] else None
                    }
                    return gps_data
            
            elif gps_line.startswith('$GPVTG'):
                # Parse VTG sentence (Course over ground and Ground speed)
                parts = gps_line.split(',')
                if len(parts) >= 9:
                    gps_data = {
                        'timestamp': time.time(),
                        'type': 'VTG',
                        'course_true': parts[1] if parts[1] else None,
                        'course_magnetic': parts[3] if parts[3] else None,
                        'speed_knots': parts[5] if parts[5] else None,
                        'speed_kmh': parts[7] if parts[7] else None,
                        'checksum': parts[8].split('*')[1] if '*' in parts[8] else None
                    }
                    return gps_data
            
            # For other NMEA sentences, save raw data
            else:
                gps_data = {
                    'timestamp': time.time(),
                    'type': 'RAW',
                    'sentence': gps_line.strip()
                }
                return gps_data
                
        except Exception as e:
            print(f"Error parsing GPS data: {e}")
            return None
    
    def gps_recording_thread(self, timestamp):
        """Thread for GPS data recording"""
        print(f"DEBUG: GPS thread starting, event_set: {self.stop_recording_event.is_set()}")
        try:
            # Open serial connection to GPS
            gps_serial = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)
            print("GPS serial connection opened")
            
            while not self.stop_recording_event.is_set():
                try:
                    # Read GPS data
                    gps_line = gps_serial.readline().decode('utf-8', errors='ignore').strip()
                    
                    if gps_line and gps_line.startswith('$'):
                        # Parse GPS data
                        gps_data = self.parse_gps_data(gps_line)
                        
                        if gps_data and self.gps_file:
                            # Save GPS data to JSON file
                            self.gps_file.write(json.dumps(gps_data) + '\n')
                            self.gps_file.flush()
                            
                            # Print GPS status (optional)
                            if gps_data.get('type') in ['GGA', 'RMC']:
                                lat = gps_data.get('latitude')
                                lon = gps_data.get('longitude')
                                if lat and lon:
                                    print(f"GPS: {lat}{gps_data.get('latitude_dir', '')}, {lon}{gps_data.get('longitude_dir', '')}")
                    
                except Exception as e:
                    print(f"Error reading GPS data: {e}")
                    time.sleep(1)  # Wait before retrying
            
            # Close serial connection
            gps_serial.close()
            print("GPS recording stopped")
            print("DEBUG: GPS thread exiting normally")
            
        except Exception as e:
            print(f"Error in GPS recording thread: {e}")
            print("DEBUG: GPS thread exiting due to error")
    
    def start_recording(self):
        """Start recording all cameras and IMU data"""
        if self.recording:
            print("Already recording!")
            return
            
        print("Starting recording...")
        self.recording = True
        
        # Clear the stop event flag for new recording
        self.stop_recording_event.clear()
        print(f"DEBUG: stop_recording_event cleared, is_set: {self.stop_recording_event.is_set()}")
        
        # Update LCD to show recording status
        try:
            set_rgb(255, 0, 0)  # Red color for recording
            set_text("RECORDING")
        except Exception as e:
            print(f"LCD update failed: {e}")
        
        # Get timestamp for this recording session
        timestamp = self.get_timestamp()
        
        # Start camera 1 (RPi camera 1)
        self.start_camera1_recording(timestamp)
        
        # Start camera 2 (RPi camera 2) 
        self.start_camera2_recording(timestamp)
        
        # Start camera 3 (DepthAI) and IMU
        self.start_depthai_recording(timestamp)
        
        print(f"Recording started - Session: {timestamp}")
        print(f"DEBUG: recording={self.recording}, event_set={self.stop_recording_event.is_set()}")
    
    def stop_recording(self):
        """Stop all recording"""
        if not self.recording:
            print("Not recording!")
            return
            
        print("Stopping recording...")
        self.recording = False
        
        # Update LCD to show ready status
        try:
            set_rgb(0, 128, 64)  # Green color for ready
            set_text("SOGO READY")
        except Exception as e:
            print(f"LCD update failed: {e}")
        
        # Stop camera processes
        self.stop_camera_processes()
        
        # Stop DepthAI recording
        self.stop_depthai_recording()
        
        print("Recording stopped")
        print(f"DEBUG: recording={self.recording}, event_set={self.stop_recording_event.is_set()}")
    
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
        """Start DepthAI camera, IMU, and GPS recording"""
        # Create IMU, gyro, skeleton, and GPS files
        imu_filename = f"imu_vector_{timestamp}.json"
        gyro_filename = f"gyroscope_{timestamp}.json"
        skeleton_filename = f"skeleton_{timestamp}.json"
        gps_filename = f"gps_{timestamp}.json"
        
        self.imu_file = open(self.recordings_dir / imu_filename, 'w')
        self.gyro_file = open(self.recordings_dir / gyro_filename, 'w')
        self.skeleton_file = open(self.recordings_dir / skeleton_filename, 'w')
        self.gps_file = open(self.recordings_dir / gps_filename, 'w')
        
        # Start DepthAI recording thread
        self.depthai_thread = threading.Thread(
            target=self.depthai_recording_thread,
            args=(timestamp,)
        )
        self.depthai_thread.daemon = True
        self.depthai_thread.start()
        
        # Start GPS recording thread
        self.gps_thread = threading.Thread(
            target=self.gps_recording_thread,
            args=(timestamp,)
        )
        self.gps_thread.daemon = True
        self.gps_thread.start()
        
        print(f"DepthAI and GPS recording started: {timestamp}")
        if self.skeleton_enabled:
            print("Skeleton recognition enabled")
        else:
            print("Skeleton recognition disabled")
    
    def depthai_recording_thread(self, timestamp):
        """Thread for DepthAI camera and IMU recording"""
        print(f"DEBUG: DepthAI thread starting, event_set: {self.stop_recording_event.is_set()}")
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
            
            # Camera properties - revert to working settings
            camRgb.setPreviewSize(1920, 1080)  # Back to original
            camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
            camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)  # Back to original
            camRgb.setInterleaved(False)
            camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
            
            # Remove problematic settings - keep it simple
            
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
                video_filename = f"camera3_{timestamp}.avi"  # Back to AVI for better timing
                video_filepath = self.recordings_dir / video_filename
                
                # Use AVI with XVID codec for normal speed
                fourcc = cv2.VideoWriter_fourcc(*'XVID')  # More reliable timing
                fps = 15.0  # Normal frame rate for smooth video
                out = cv2.VideoWriter(str(video_filepath), fourcc, fps, (1920, 1080))  # Back to original
                
                if not out.isOpened():
                    print("Error: Could not initialize video writer")
                    return
                
                print(f"DepthAI video recording: {video_filename} at {fps} FPS (smooth video)")
                
                # Timing for smooth video
                frame_interval = 1.0 / fps
                last_frame_time = time.time()
                frame_count = 0
                
                while not self.stop_recording_event.is_set():
                    inRgb = qRgb.tryGet()
                    inImu = qImu.tryGet()
                    
                    if inRgb is not None:
                        frame = inRgb.getCvFrame()
                        
                        # Frame processing for smooth video
                        current_time = time.time()
                        time_since_last = current_time - last_frame_time
                        
                        # Process frames at 15 FPS for smooth video
                        if time_since_last >= frame_interval:
                            last_frame_time = current_time
                            frame_count += 1
                            
                            # Add timestamp
                            timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            cv2.putText(frame, timestamp_str, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                            
                            # Add frame counter for debugging
                            cv2.putText(frame, f"Frame: {frame_count} (15 FPS)", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                            
                            # Skeleton detection and processing
                            if self.skeleton_enabled and self.pose_detector:
                                try:
                                    # Convert BGR to RGB for MediaPipe
                                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                    
                                    # Create MediaPipe image
                                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                                    
                                    # Detect pose landmarks
                                    detection_result = self.pose_detector.detect(mp_image)
                                    
                                    # Draw landmarks on frame
                                    frame_with_skeleton = self.draw_landmarks_on_frame(frame, detection_result)
                                    
                                    # Process and save skeleton data
                                    self.process_skeleton_data(detection_result, current_time)
                                    
                                    # Write frame with skeleton overlay
                                    out.write(frame_with_skeleton)
                                    
                                except Exception as e:
                                    print(f"Error in skeleton processing: {e}")
                                    # Fallback to original frame
                                    out.write(frame)
                            else:
                                # Write original frame if skeleton is disabled
                                out.write(frame)
                            
                            # Small sleep to maintain timing
                            time.sleep(0.01)  # 10ms sleep for 15 FPS
                    
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
                print("DEBUG: DepthAI thread exiting normally")
                
        except Exception as e:
            print(f"Error in DepthAI recording thread: {e}")
            print("DEBUG: DepthAI thread exiting due to error")
    
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
        """Stop DepthAI and GPS recording"""
        self.stop_recording_event.set()
        
        if self.depthai_thread:
            self.depthai_thread.join(timeout=5)
        
        if self.gps_thread:
            self.gps_thread.join(timeout=5)
        
        if self.imu_file:
            self.imu_file.close()
            self.imu_file = None
        
        if self.gyro_file:
            self.gyro_file.close()
            self.gyro_file = None
        
        if self.skeleton_file:
            self.skeleton_file.close()
            self.skeleton_file = None
        
        if self.gps_file:
            self.gps_file.close()
            self.gps_file = None
        
        print("DepthAI and GPS recording stopped")
    
    def cleanup(self):
        """Cleanup resources"""
        if self.recording:
            self.stop_recording()
        
        print("Cleanup completed")
    
    def run(self):
        """Main run loop"""
        try:
            print("Multi-Camera Recording System Ready (No GPIO)")
            print("Press Enter to start/stop recording")
            print("Press Ctrl+C to exit")
            
            # Keep the main thread alive and check for Enter key
            while True:
                try:
                    user_input = input()
                    if user_input.strip() == "":
                        if not self.recording:
                            print(f"DEBUG: Starting recording, event_set: {self.stop_recording_event.is_set()}")
                            self.start_recording()
                        else:
                            print(f"DEBUG: Stopping recording, event_set: {self.stop_recording_event.is_set()}")
                            self.stop_recording()
                except EOFError:
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