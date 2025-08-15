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
            "cam1": deque(),
            "cam2": deque(), 
            "cam3": deque()
        }
        
        # Camera processes and threads
        self.camera1_process = None
        self.camera2_process = None
        self.depthai_device = None
        self.depthai_thread = None
        
        # Thread locks for thread safety
        self.frame_locks = {
            "cam1": threading.Lock(),
            "cam2": threading.Lock(),
            "cam3": threading.Lock()
        }
        
        # Shared sampling control - simple approach
        self.sample_interval = 0.5
        self.next_sample_time = 0
        self.sampling_lock = threading.Lock()
        self.sample_event = threading.Event()  # Event to signal all cameras to sample
        
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
        
        # Clean up any existing camera processes
        self.cleanup_existing_cameras()
        
        # Don't check cameras here - they might be in use
        print("Camera availability will be checked when recording starts")
    
    def check_ffmpeg(self):
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            print("✅ ffmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ ffmpeg not found. Please install ffmpeg")
    
    def cleanup_existing_cameras(self):
        """Kill any existing camera processes that might be using the cameras"""
        print("Cleaning up any existing camera processes...")
        
        try:
            # Kill any rpicam-vid processes
            result = subprocess.run("pkill -f rpicam-vid", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Killed existing rpicam-vid processes")
            else:
                print("ℹ️  No existing rpicam-vid processes found")
            
            # Wait a moment for processes to be killed
            time.sleep(2.0)
            
            # Also try to kill any libcamera processes
            result = subprocess.run("pkill -f libcamera", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Killed existing libcamera processes")
            
            time.sleep(1.0)
            
        except Exception as e:
            print(f"Warning: Could not cleanup processes: {e}")
        
        print("Camera cleanup complete")
    
    def get_timestamp(self):
        """Get current timestamp for filenames"""
        return datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    def initialize_sampling_time(self):
        """Initialize the next sampling time based on OS clock"""
        current_time = time.time()
        # Calculate the next 0.5-second boundary
        self.next_sample_time = ((current_time // self.sample_interval) + 1) * self.sample_interval
        self.sample_count = 0
        print(f"🕐 Next sample at: {datetime.datetime.fromtimestamp(self.next_sample_time).strftime('%H:%M:%S.%f')[:-3]}")
        print(f"🕐 Current time: {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}")
        print(f"🕐 Time until next sample: {self.next_sample_time - current_time:.3f}s")
    
    def start_sampling_timer(self):
        """Start a timer thread that signals all cameras to sample at the right time"""
        def timer_thread():
            while self.sampling_active and not self.stop_event.is_set():
                current_time = time.time()
                if current_time >= self.next_sample_time:
                    print(f"⏰ TIMER: Signaling all cameras to sample at {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}")
                    self.sample_event.set()  # Signal all cameras to sample
                    self.next_sample_time += self.sample_interval
                    time.sleep(0.3)  # Wait for all cameras to receive the signal
                    self.sample_event.clear()  # Clear the event for next time
                    time.sleep(0.1)  # Small delay before next cycle
                else:
                    time.sleep(0.01)  # Check every 10ms
        
        timer = threading.Thread(target=timer_thread)
        timer.daemon = True
        timer.start()
        return timer
    
    def should_sample_now(self):
        """Check if it's time to sample and log timing details"""
        current_time = time.time()
        time_until_sample = self.next_sample_time - current_time
        
        if current_time >= self.next_sample_time:
            print(f"⏰ SAMPLING TRIGGERED - Current: {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}, Next: {datetime.datetime.fromtimestamp(self.next_sample_time).strftime('%H:%M:%S.%f')[:-3]}")
            return True
        else:
            if self.sampling_active and time_until_sample < 0.1:  # Log when close to sampling
                print(f"⏰ Waiting for sample - Time until: {time_until_sample:.3f}s")
            return False
    
    def update_next_sample_time(self):
        """Update the next sample time - only called by the first camera that samples"""
        with self.sampling_lock:
            self.next_sample_time += self.sample_interval
            print(f"🔄 Updated next sample time to: {datetime.datetime.fromtimestamp(self.next_sample_time).strftime('%H:%M:%S.%f')[:-3]}")
    
    def start_camera_threads(self):
        """Start all camera threads for frame sampling"""
        print("Starting camera threads for frame sampling...")
        
        # Start CSI Camera 1 (camera 0)
        print("Starting CSI Camera 1...")
        self.camera_threads["cam1"] = threading.Thread(target=self.csi_camera1_thread)
        self.camera_threads["cam1"].daemon = True
        self.camera_threads["cam1"].start()
        
        # Wait for camera 1 to fully start before starting camera 2
        time.sleep(3.0)
        
        # Start CSI Camera 2 (camera 1)
        print("Starting CSI Camera 2...")
        self.camera_threads["cam2"] = threading.Thread(target=self.csi_camera2_thread)
        self.camera_threads["cam2"].daemon = True
        self.camera_threads["cam2"].start()
        
        # Wait for camera 2 to fully start before starting DepthAI
        time.sleep(3.0)
        
        # Start DepthAI Camera
        print("Starting DepthAI Camera...")
        self.camera_threads["cam3"] = threading.Thread(target=self.depthai_camera_thread)
        self.camera_threads["cam3"].daemon = True
        self.camera_threads["cam3"].start()
        
        print("All camera threads started and ready for sampling")
    
    def csi_camera1_thread(self):
        """Thread for CSI Camera 1 (camera 0) frame sampling"""
        print("CSI Camera 1 thread starting...")
        
        # Kill any existing rpicam-vid processes for camera 0
        try:
            subprocess.run("pkill -f 'rpicam-vid.*camera 0'", shell=True, capture_output=True)
            time.sleep(1.0)  # Wait for process to be killed
            print("Killed any existing camera 0 processes")
        except Exception as e:
            print(f"Warning: Could not kill existing processes: {e}")
        
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
            
            print("CSI Camera 1 monitoring loop started")
            
            while not self.stop_event.is_set():
                current_time = time.time()
                
                # Check if process is still running
                if process.poll() is not None:
                    print("❌ CSI Camera 1 process stopped unexpectedly")
                    break
                
                # Wait for sampling signal from timer
                if self.sampling_active:
                    # Wait for the sampling event (with timeout to check stop_event)
                    if self.sample_event.wait(timeout=0.1):
                        should_sample = True
                        print(f"📸 cam1: Received sampling signal at {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}")
                    else:
                        should_sample = False
                else:
                    should_sample = False
                
                if should_sample:
                    print(f"📸 cam1: Starting frame capture at {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}...")
                    # Check if MJPEG file exists and has content
                    if mjpeg_filepath.exists() and mjpeg_filepath.stat().st_size > 0:
                        print(f"📁 cam1: MJPEG file exists, size: {mjpeg_filepath.stat().st_size} bytes")
                        # Read the latest frame from the MJPEG file
                        cap = cv2.VideoCapture(str(mjpeg_filepath))
                        if cap.isOpened():
                            print(f"🎥 cam1: VideoCapture opened successfully")
                            ret, frame = cap.read()
                            if ret:
                                print(f"✅ cam1: Frame read successfully, shape: {frame.shape}")
                                # Add timestamp, frame number, and camera label
                                timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                                cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                                cv2.putText(frame, timestamp_str, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                                cv2.putText(frame, "CAM1", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                                
                                with self.frame_locks["cam1"]:
                                    self.camera_frames["cam1"].append({
                                        'frame': frame.copy(),
                                        'frame_number': frame_count,
                                        'timestamp': current_time,
                                        'timestamp_str': timestamp_str
                                    })
                                    print(f"[SAMPLING] cam1: {len(self.camera_frames['cam1'])} frames at {timestamp_str}")
                                frame_count += 1
                            else:
                                print(f"❌ cam1: Failed to read frame from MJPEG file")
                            cap.release()
                        else:
                            print(f"❌ cam1: Failed to open MJPEG file for reading")
                    else:
                        print(f"❌ cam1: MJPEG file not ready (exists: {mjpeg_filepath.exists()}, size: {mjpeg_filepath.stat().st_size if mjpeg_filepath.exists() else 0})")
                else:
                    # Debug: show when not sampling
                    if self.sampling_active:
                        time_until = self.next_sample_time - current_time
                        if time_until < 0.1:  # Only log when close to sampling
                            print(f"⏳ cam1: Waiting for next sample interval ({time_until:.3f}s until next)")
                
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
        
        # Kill any existing rpicam-vid processes for camera 1
        try:
            subprocess.run("pkill -f 'rpicam-vid.*camera 1'", shell=True, capture_output=True)
            time.sleep(1.0)
            print("Killed any existing camera 1 processes")
        except Exception as e:
            print(f"Warning: Could not kill existing processes: {e}")
        
        # Use rpicam-vid to record MJPEG and extract frames
        timestamp = self.get_timestamp()
        mjpeg_filename = f"camera2_{timestamp}.mjpeg"
        mjpeg_filepath = self.recordings_dir / mjpeg_filename
        
        # Command to record MJPEG - use camera 1
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
            time.sleep(2.0)
            
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"❌ CSI Camera 2 failed to start. stderr: {stderr.decode()}")
                return
            
            # Wait longer for MJPEG file to be created
            print("⏳ Waiting for cam2 MJPEG file to be created...")
            max_wait_time = 15.0  # Wait up to 15 seconds
            wait_start = time.time()
            while not mjpeg_filepath.exists() and (time.time() - wait_start) < max_wait_time:
                time.sleep(0.5)
                print(f"⏳ Still waiting for cam2 MJPEG file... ({time.time() - wait_start:.1f}s)")
            
            # Check if MJPEG file is being created
            if mjpeg_filepath.exists():
                initial_size = mjpeg_filepath.stat().st_size
                print(f"✅ cam2: MJPEG file created, initial size: {initial_size} bytes")
            else:
                print(f"❌ cam2: MJPEG file not created after {max_wait_time}s")
                # Check if process is still running
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print(f"❌ cam2: Process failed. stderr: {stderr.decode()}")
                    return
                else:
                    print(f"⚠️ cam2: Process still running but no file created - continuing anyway")
            
            print("✅ CSI Camera 2 recording started successfully")
            
            # Extract frames from MJPEG file every 0.5 seconds
            frame_count = 0
            
            print("CSI Camera 2 monitoring loop started")
            
            while not self.stop_event.is_set():
                current_time = time.time()
                
                # Check if process is still running
                if process.poll() is not None:
                    print("❌ CSI Camera 2 process stopped unexpectedly")
                    break
                
                # Wait for sampling signal from timer
                if self.sampling_active:
                    # Wait for the sampling event (with timeout to check stop_event)
                    if self.sample_event.wait(timeout=0.1):
                        should_sample = True
                        print(f"📸 cam2: Received sampling signal at {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}")
                    else:
                        should_sample = False
                else:
                    should_sample = False
                
                if should_sample:
                    print(f"📸 cam2: Starting frame capture at {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}...")
                    # Check if MJPEG file exists and has content
                    current_size = mjpeg_filepath.stat().st_size if mjpeg_filepath.exists() else 0
                    if mjpeg_filepath.exists() and current_size > 0:
                        print(f"📁 cam2: MJPEG file exists, size: {current_size} bytes")
                        # Read the latest frame from the MJPEG file
                        cap = cv2.VideoCapture(str(mjpeg_filepath))
                        if cap.isOpened():
                            print(f"🎥 cam2: VideoCapture opened successfully")
                            ret, frame = cap.read()
                            if ret:
                                print(f"✅ cam2: Frame read successfully, shape: {frame.shape}")
                                # Add timestamp, frame number, and camera label
                                timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                                cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                                cv2.putText(frame, timestamp_str, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                                cv2.putText(frame, "CAM2", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                                
                                with self.frame_locks["cam2"]:
                                    self.camera_frames["cam2"].append({
                                        'frame': frame.copy(),
                                        'frame_number': frame_count,
                                        'timestamp': current_time,
                                        'timestamp_str': timestamp_str
                                    })
                                    print(f"[SAMPLING] cam2: {len(self.camera_frames['cam2'])} frames at {timestamp_str}")
                                frame_count += 1
                            else:
                                print(f"❌ cam2: Failed to read frame from MJPEG file")
                            cap.release()
                        else:
                            print(f"❌ cam2: Failed to open MJPEG file for reading")
                    else:
                        print(f"❌ cam2: MJPEG file not ready (exists: {mjpeg_filepath.exists()}, size: {current_size})")
                else:
                    # Debug: show when not sampling
                    if self.sampling_active:
                        time_until = self.next_sample_time - current_time
                        if time_until < 0.1:  # Only log when close to sampling
                            print(f"⏳ cam2: Waiting for next sample interval ({time_until:.3f}s until next)")
                
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
                
                while not self.stop_event.is_set():
                    inRgb = qRgb.tryGet()
                    
                    if inRgb is not None:
                        frame = inRgb.getCvFrame()
                        current_time = time.time()
                        
                        # Add timestamp, frame number, and camera label
                        timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                        cv2.putText(frame, timestamp_str, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
                        cv2.putText(frame, "CAM3", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                        
                        # Wait for sampling signal from timer
                        if self.sampling_active:
                            # Wait for the sampling event (with timeout to check stop_event)
                            if self.sample_event.wait(timeout=0.1):
                                should_sample = True
                                print(f"📸 cam3: Received sampling signal at {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}")
                            else:
                                should_sample = False
                        else:
                            should_sample = False
                        
                        if should_sample:
                            print(f"📸 cam3: Starting frame capture at {datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]}...")
                            with self.frame_locks["cam3"]:
                                self.camera_frames["cam3"].append({
                                    'frame': frame.copy(),
                                    'frame_number': frame_count,
                                    'timestamp': current_time,
                                    'timestamp_str': timestamp_str
                                })
                                print(f"[SAMPLING] cam3: {len(self.camera_frames['cam3'])} frames at {timestamp_str}")
                            print(f"✅ cam3: Frame captured successfully, shape: {frame.shape}")
                        
                        frame_count += 1
                    
                    # Small delay to maintain frame rate
                    time.sleep(0.01)
                
        except Exception as e:
            print(f"Error in DepthAI camera thread: {e}")
        
        print("DepthAI camera thread stopped")
    
    def start_sampling(self):
        """Start frame sampling from all cameras"""
        print("🚀 Starting frame sampling from all cameras...")
        self.sampling_active = True
        
        # Initialize sampling time
        print("⏰ Initializing sampling timing...")
        self.initialize_sampling_time()
        print(f"✅ Sampling initialized - will sample every {self.sample_interval} seconds")
        
        # Start the sampling timer
        self.sampling_timer = self.start_sampling_timer()
        print("⏰ Sampling timer started")
        
        # Update LCD
        if LCD_AVAILABLE:
            try:
                set_rgb(255, 0, 0)  # Red color for recording
                set_text("SAMPLING")
            except Exception as e:
                print(f"LCD update failed: {e}")
        
        print("🎬 Frame sampling active. Press Enter to stop sampling and create videos...")
    
    def stop_sampling(self):
        """Stop frame sampling and create videos"""
        print("\nStopping frame sampling...")
        self.sampling_active = False
        self.stop_event.set()
        
        # Stop the sampling timer
        if hasattr(self, 'sampling_timer'):
            print("Stopping sampling timer...")
        
        # Wait for all camera threads to finish
        print("Waiting for camera threads to finish...")
        for camera_name, thread in self.camera_threads.items():
            if thread.is_alive():
                print(f"Waiting for {camera_name} thread to finish...")
                thread.join(timeout=5.0)
                if thread.is_alive():
                    print(f"Warning: {camera_name} thread did not finish gracefully")
        
        print("Creating videos from sampled frames...")
        self.create_videos()
    
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
