#!/usr/bin/env python3
"""
Multi-Camera Recording System with IMU Data Collection and Skeleton Recognition (Button Control)
Integrates: 3 cameras (2 RPi cameras + 1 DepthAI), IMU data, Grove LCD RGB, Skeleton Recognition
Button control - for production use with physical button
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
from pathlib import Path
from grove_lcd_rgb import set_text, set_rgb

# MediaPipe imports for skeleton recognition
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions

# GPIO button imports
from gpiozero import Button
from signal import pause

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
        
        # File handles
        self.imu_file = None
        self.gyro_file = None
        self.skeleton_file = None
        self.camera1_file = None
        self.camera2_file = None
        self.camera3_file = None
        
        # Skeleton recognition
        self.pose_detector = None
        self.skeleton_enabled = True  # Toggle for skeleton detection
        
        # Initialize skeleton recognition
        self.initialize_pose_detector()
        
        # Initialize button
        self.button = Button(17)  # GPIO17
        self.button.when_pressed = self.button_pressed
        
        # Initialize LCD
        try:
            set_rgb(0, 128, 64)  # Green color
            set_text("SOGO READY")
            print("LCD initialized successfully")
        except Exception as e:
            print(f"LCD initialization failed: {e}")
        
        print("Multi-Camera Recording System Initialized (Button Control)")
        print("Press button on GPIO17 to start/stop recording")
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
    
    def button_pressed(self):
        """Handle button press - toggle recording"""
        if not self.recording:
            print("Button pressed - Starting recording...")
            self.start_recording()
        else:
            print("Button pressed - Stopping recording...")
            self.stop_recording()
    
    def start_recording(self):
        """Start recording all cameras and IMU data"""
        if self.recording:
            print("Already recording!")
            return
            
        print("Starting recording...")
        self.recording = True
        
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
        skeleton_filename = f"skeleton_{timestamp}.json"
        
        self.imu_file = open(self.recordings_dir / imu_filename, 'w')
        self.gyro_file = open(self.recordings_dir / gyro_filename, 'w')
        self.skeleton_file = open(self.recordings_dir / skeleton_filename, 'w')
        
        # Start DepthAI recording thread
        self.depthai_thread = threading.Thread(
            target=self.depthai_recording_thread,
            args=(timestamp,)
        )
        self.depthai_thread.daemon = True
        self.depthai_thread.start()
        
        print(f"DepthAI recording started: {timestamp}")
        if self.skeleton_enabled:
            print("Skeleton recognition enabled")
        else:
            print("Skeleton recognition disabled")
    
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
        
        if self.skeleton_file:
            self.skeleton_file.close()
            self.skeleton_file = None
        
        print("DepthAI recording stopped")
    
    def cleanup(self):
        """Cleanup resources"""
        if self.recording:
            self.stop_recording()
        
        print("Cleanup completed")
    
    def run(self):
        """Main run loop with button control"""
        try:
            print("Multi-Camera Recording System Ready (Button Control)")
            print("Press button on GPIO17 to start/stop recording")
            print("Press Ctrl+C to exit")
            
            # Keep the main thread alive and wait for button presses
            while True:
                time.sleep(0.1)  # Small sleep to prevent high CPU usage
                
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