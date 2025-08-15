#!/usr/bin/env python3
"""
Synchronized Multi-Camera Recording System
Samples frames from all cameras simultaneously and creates synchronized videos
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
from collections import deque
import numpy as np

# LCD Display (optional)
try:
    from grove_lcd_rgb import set_text, set_rgb
    LCD_AVAILABLE = True
    print("LCD display enabled")
except Exception as e:
    print(f"LCD display not available: {e}")
    
    # Create dummy functions if LCD is not available
    def set_text(text):
        print(f"LCD: {text}")
    
    def set_rgb(r, g, b):
        print(f"LCD RGB: ({r}, {g}, {b})")

# Suppress TensorFlow warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

class SynchronizedRecorder:
    def __init__(self):
        self.recording = False
        self.sampling_active = False
        self.stop_event = threading.Event()
        
        # Recording paths
        self.recordings_dir = Path("recordings")
        self.recordings_dir.mkdir(exist_ok=True)
        
        # Frame buffers for each camera
        self.camera_frames = {
            "CSI Cam 0": deque(),
            "CSI Cam 1": deque(), 
            "DepthAI Cam": deque()
        }
        
        # Camera processes and threads
        self.camera1_process = None
        self.camera2_process = None
        self.depthai_device = None
        self.depthai_thread = None
        
        # Thread locks for thread safety
        self.frame_locks = {
            "CSI Cam 0": threading.Lock(),
            "CSI Cam 1": threading.Lock(),
            "DepthAI Cam": threading.Lock()
        }
        
        # Initialize LCD
        if LCD_AVAILABLE:
            try:
                set_rgb(0, 128, 64)  # Green color
                set_text("SOGO READY")
                print("LCD initialized successfully")
            except Exception as e:
                print(f"LCD initialization failed: {e}")
        else:
            print("LCD not available - using console output")
        
        print("Synchronized Multi-Camera Recording System Initialized")
        print("Press Enter to start frame sampling")
        print("Press Enter again to stop sampling and create videos")
        print("Press Ctrl+C to exit")
        
        # Check for ffmpeg
        self.check_ffmpeg()
        
        # Don't check cameras here - they might be in use
        print("Camera availability will be checked when recording starts")
    
    def check_ffmpeg(self):
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            print("✅ ffmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ ffmpeg not found. Please install ffmpeg")
    
    def check_available_cameras(self):
        """Check what cameras are available on the system"""
        print("[INFO] Checking available cameras...")
        
        # Check only the 2 CSI cameras we actually use
        csi_cameras = []
        for i in range(2):  # Only check camera 0 and 1
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                try:
                    cap = cv2.VideoCapture(device_path)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret:
                            print(f"✅ CSI Camera {i} found at {device_path}")
                            csi_cameras.append(device_path)
                        else:
                            print(f"⚠️  CSI Camera {i} at {device_path} - device exists but no frame")
                    else:
                        print(f"❌ CSI Camera {i} at {device_path} - device exists but not accessible")
                    cap.release()
                except Exception as e:
                    print(f"❌ CSI Camera {i} at {device_path} - Error: {e}")
            else:
                print(f"❌ CSI Camera {i} at {device_path} - not found")
        
        # Check DepthAI camera
        try:
            # Try to create a simple DepthAI pipeline to test
            pipeline = dai.Pipeline()
            cam = pipeline.create(dai.node.ColorCamera)
            cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
            cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
            
            xout = pipeline.create(dai.node.XLinkOut)
            xout.setStreamName("video")
            cam.video.link(xout.input)
            
            device = dai.Device(pipeline)
            print("✅ DepthAI camera found and accessible")
            device.close()
        except Exception as e:
            print(f"❌ DepthAI camera not available: {e}")
        
        print(f"[SUMMARY] Found {len(csi_cameras)} working CSI cameras: {csi_cameras}")
        return csi_cameras
    
    def get_timestamp(self):
        """Get current timestamp for filenames"""
        return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def start_camera_threads(self):
        """Start all camera threads for frame sampling"""
        print("Starting camera threads for frame sampling...")
        
        # Start CSI camera threads with delays to avoid conflicts
        self.camera1_thread = threading.Thread(target=self.csi_camera1_thread, daemon=True)
        self.camera2_thread = threading.Thread(target=self.csi_camera2_thread, daemon=True)
        
        # Start DepthAI thread
        self.depthai_thread = threading.Thread(target=self.depthai_camera_thread, daemon=True)
        
        # Start threads with delays to avoid camera conflicts
        print("Starting CSI Camera 1...")
        self.camera1_thread.start()
        time.sleep(2.0)  # Wait 2 seconds between camera starts
        
        print("Starting CSI Camera 2...")
        self.camera2_thread.start()
        time.sleep(2.0)  # Wait 2 seconds between camera starts
        
        print("Starting DepthAI Camera...")
        self.depthai_thread.start()
        
        # Wait for threads to initialize
        time.sleep(2.0)
        print("All camera threads started and ready for sampling")
    
    def csi_camera1_thread(self):
        """Thread for CSI Camera 1 (camera 0) frame sampling"""
        print("CSI Camera 1 thread starting...")
        
        # Use rpicam-vid to record MJPEG and extract frames
        timestamp = self.get_timestamp()
        mjpeg_filename = f"camera1_{timestamp}.mjpeg"
        mjpeg_filepath = self.recordings_dir / mjpeg_filename
        
        # Command to record MJPEG
        cmd = f"rpicam-vid --camera 0 --codec mjpeg --nopreview --inline -o {mjpeg_filepath}"
        
        try:
            print(f"Starting CSI Camera 1 recording: {cmd}")
            
            # Start rpicam-vid process
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            # Wait for file to start being created
            time.sleep(1.0)
            
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"❌ CSI Camera 1 failed to start. stderr: {stderr.decode()}")
                print("Trying alternative approach...")
                
                # Try with different parameters
                alt_cmd = f"rpicam-vid --camera 0 --codec mjpeg --nopreview --inline --timeout 0 -o {mjpeg_filepath}"
                print(f"Retrying with: {alt_cmd}")
                
                process = subprocess.Popen(
                    alt_cmd, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                time.sleep(2.0)
                
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print(f"❌ CSI Camera 1 failed with alternative approach. stderr: {stderr.decode()}")
                    return
            
            print("✅ CSI Camera 1 recording started successfully")
            
            # Extract frames from MJPEG file every 0.5 seconds
            frame_count = 0
            last_sample_time = 0
            sample_interval = 0.5
            
            while not self.stop_event.is_set() and process.poll() is None:
                current_time = time.time()
                
                # Sample frame if sampling is active and 0.5 seconds have passed
                if self.sampling_active and (current_time - last_sample_time) >= sample_interval:
                    # Read the latest frame from the MJPEG file
                    cap = cv2.VideoCapture(str(mjpeg_filepath))
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret:
                            # Add timestamp and frame number
                            timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                            cv2.putText(frame, timestamp_str, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                            
                            with self.frame_locks["CSI Cam 0"]:
                                self.camera_frames["CSI Cam 0"].append({
                                    'frame': frame.copy(),
                                    'frame_number': frame_count,
                                    'timestamp': current_time,
                                    'timestamp_str': timestamp_str
                                })
                                print(f"[SAMPLING] CSI Cam 0: {len(self.camera_frames['CSI Cam 0'])} frames at {timestamp_str}")
                            last_sample_time = current_time
                            frame_count += 1
                        cap.release()
                
                time.sleep(0.1)  # Check every 100ms
            
            # Stop the process
            process.terminate()
            process.wait()
            
        except Exception as e:
            print(f"❌ Error in CSI Camera 1 thread: {e}")
        
        print("CSI Camera 1 thread stopped")
    
    def csi_camera2_thread(self):
        """Thread for CSI Camera 2 (camera 1) frame sampling"""
        print("CSI Camera 2 thread starting...")
        
        # Use rpicam-vid to record MJPEG and extract frames
        timestamp = self.get_timestamp()
        mjpeg_filename = f"camera2_{timestamp}.mjpeg"
        mjpeg_filepath = self.recordings_dir / mjpeg_filename
        
        # Command to record MJPEG
        cmd = f"rpicam-vid --camera 1 --codec mjpeg --nopreview --inline -o {mjpeg_filepath}"
        
        try:
            print(f"Starting CSI Camera 2 recording: {cmd}")
            
            # Start rpicam-vid process
            process = subprocess.Popen(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            # Wait for file to start being created
            time.sleep(1.0)
            
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"❌ CSI Camera 2 failed to start. stderr: {stderr.decode()}")
                print("Trying alternative approach...")
                
                # Try with different parameters
                alt_cmd = f"rpicam-vid --camera 1 --codec mjpeg --nopreview --inline --timeout 0 -o {mjpeg_filepath}"
                print(f"Retrying with: {alt_cmd}")
                
                process = subprocess.Popen(
                    alt_cmd, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )
                
                time.sleep(2.0)
                
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print(f"❌ CSI Camera 2 failed with alternative approach. stderr: {stderr.decode()}")
                    return
            
            print("✅ CSI Camera 2 recording started successfully")
            
            # Extract frames from MJPEG file every 0.5 seconds
            frame_count = 0
            last_sample_time = 0
            sample_interval = 0.5
            
            while not self.stop_event.is_set() and process.poll() is None:
                current_time = time.time()
                
                # Sample frame if sampling is active and 0.5 seconds have passed
                if self.sampling_active and (current_time - last_sample_time) >= sample_interval:
                    # Read the latest frame from the MJPEG file
                    cap = cv2.VideoCapture(str(mjpeg_filepath))
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret:
                            # Add timestamp and frame number
                            timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                            cv2.putText(frame, timestamp_str, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                            
                            with self.frame_locks["CSI Cam 1"]:
                                self.camera_frames["CSI Cam 1"].append({
                                    'frame': frame.copy(),
                                    'frame_number': frame_count,
                                    'timestamp': current_time,
                                    'timestamp_str': timestamp_str
                                })
                                print(f"[SAMPLING] CSI Cam 1: {len(self.camera_frames['CSI Cam 1'])} frames at {timestamp_str}")
                            last_sample_time = current_time
                            frame_count += 1
                        cap.release()
                
                time.sleep(0.1)  # Check every 100ms
            
            # Stop the process
            process.terminate()
            process.wait()
            
        except Exception as e:
            print(f"❌ Error in CSI Camera 2 thread: {e}")
        
        print("CSI Camera 2 thread stopped")
    
    def depthai_camera_thread(self):
        """Thread for DepthAI camera frame sampling"""
        print("DepthAI camera thread starting...")
        
        try:
            # Create pipeline
            pipeline = dai.Pipeline()
            
            # Define sources and outputs
            camRgb = pipeline.create(dai.node.ColorCamera)
            xlinkOut = pipeline.create(dai.node.XLinkOut)
            
            xlinkOut.setStreamName("rgb")
            
            # Camera properties
            camRgb.setPreviewSize(640, 480)
            camRgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
            camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
            camRgb.setInterleaved(False)
            camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
            
            # Linking
            camRgb.preview.link(xlinkOut.input)
            
            # Connect to device
            with dai.Device(pipeline) as device:
                print("DepthAI device connected successfully!")
                
                # Output queue
                qRgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
                
                frame_count = 0
                last_sample_time = 0
                sample_interval = 0.5  # Sample every 0.5 seconds
                
                while not self.stop_event.is_set():
                    inRgb = qRgb.tryGet()
                    
                    if inRgb is not None:
                        frame = inRgb.getCvFrame()
                        current_time = time.time()
                        
                        # Add timestamp and frame number
                        timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                        cv2.putText(frame, timestamp_str, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                        
                        # Sample frame if sampling is active and 0.5 seconds have passed
                        if self.sampling_active and (current_time - last_sample_time) >= sample_interval:
                            with self.frame_locks["DepthAI Cam"]:
                                self.camera_frames["DepthAI Cam"].append({
                                    'frame': frame.copy(),
                                    'frame_number': frame_count,
                                    'timestamp': current_time,
                                    'timestamp_str': timestamp_str
                                })
                                print(f"[SAMPLING] DepthAI Cam: {len(self.camera_frames['DepthAI Cam'])} frames at {timestamp_str}")
                            last_sample_time = current_time
                        
                        frame_count += 1
                    
                    # Small delay to maintain frame rate
                    time.sleep(0.01)
                
        except Exception as e:
            print(f"Error in DepthAI camera thread: {e}")
        
        print("DepthAI camera thread stopped")
    
    def start_sampling(self):
        """Start frame sampling from all cameras"""
        print("Starting frame sampling from all cameras...")
        self.sampling_active = True
        
        # Update LCD
        if LCD_AVAILABLE:
            try:
                set_rgb(255, 0, 0)  # Red color for recording
                set_text("SAMPLING")
            except Exception as e:
                print(f"LCD update failed: {e}")
        
        print("Frame sampling active. Press Enter to stop sampling and create videos...")
    
    def stop_sampling(self):
        """Stop frame sampling and create videos"""
        print("Stopping frame sampling...")
        self.sampling_active = False
        
        # Update LCD
        if LCD_AVAILABLE:
            try:
                set_rgb(0, 128, 64)  # Green color for ready
                set_text("PROCESSING")
            except Exception as e:
                print(f"LCD update failed: {e}")
        
        # Create videos from sampled frames
        self.create_videos_from_samples()
    
    def create_videos_from_samples(self):
        """Create videos from the sampled frames"""
        print("Creating videos from sampled frames...")
        
        timestamp = self.get_timestamp()
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        for camera_name, frames in self.camera_frames.items():
            if len(frames) == 0:
                print(f"[WARNING] No frames captured for {camera_name}")
                continue
            
            # Create video filename
            video_filename = f"{camera_name.replace(' ', '_').lower()}_{timestamp}.mp4"
            video_filepath = self.recordings_dir / video_filename
            
            # Get frame dimensions from first frame
            first_frame = frames[0]['frame']
            height, width = first_frame.shape[:2]
            
            # Create video writer
            out = cv2.VideoWriter(str(video_filepath), fourcc, 30, (width, height))
            
            print(f"[PROCESSING] Creating video for {camera_name}: {len(frames)} frames")
            
            # Write all frames to video
            for frame_data in frames:
                out.write(frame_data['frame'])
            
            out.release()
            print(f"[SUCCESS] Video saved: {video_filepath}")
        
        print("[DONE] All videos created successfully!")
        
        # Update LCD
        if LCD_AVAILABLE:
            try:
                set_rgb(0, 128, 64)  # Green color for ready
                set_text("SOGO READY")
            except Exception as e:
                print(f"LCD update failed: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        print("Cleaning up...")
        self.stop_event.set()
        
        if self.depthai_device:
            self.depthai_device.close()
        
        print("Cleanup complete")
    
    def run(self):
        """Main run loop"""
        try:
            # Start camera threads
            self.start_camera_threads()
            
            # Main loop
            while True:
                try:
                    input("Press Enter to start frame sampling...")
                    self.start_sampling()
                    
                    input("Press Enter to stop sampling and create videos...")
                    self.stop_sampling()
                    
                    # Ask if user wants to continue
                    response = input("Press Enter to start new recording, or 'q' to quit: ")
                    if response.lower() == 'q':
                        break
                    
                    # Clear frame buffers for next recording
                    for camera_name in self.camera_frames:
                        with self.frame_locks[camera_name]:
                            self.camera_frames[camera_name].clear()
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Error in main loop: {e}")
                    break
        
        finally:
            self.cleanup()

def main():
    recorder = SynchronizedRecorder()
    recorder.run()

if __name__ == "__main__":
    main()
