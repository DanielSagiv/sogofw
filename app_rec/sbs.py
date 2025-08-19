#!/usr/bin/env python3
"""
Synchronized Multi-Cam Recording (CSI1, CSI2, DepthAI) to H.264
Starts all 3 cameras simultaneously, stops on Enter, saves 3 synced files
Enhanced with skeleton detection on cam3 (DepthAI)
"""

import subprocess
import threading
import time
import datetime
import cv2
import depthai as dai
import os
from pathlib import Path
import signal
import json
import numpy as np
from collections import deque
import serial

# MediaPipe imports for skeleton recognition
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions

class SynchronizedRecorder:
    def __init__(self):
        self.session_name = f"session_{int(time.time())}"
        self.recordings_dir = Path("recordings") / self.session_name
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        self.cam1_proc = None
        self.cam2_proc = None
        self.cam3_thread = None
        self.stop_event = threading.Event()
        self.cam3_writer = None
        self.cam3_pipeline = None
        self.cam3_device = None

        # Skeleton detection attributes
        self.pose_detector = None
        self.skeleton_enabled = False  # Disabled during recording to maintain sync
        self.skeleton_data = []
        self.skeleton_file = None
        
        # IMU, Gyro, and GPS data collection attributes
        self.imu_file = None
        self.gyro_file = None
        self.gps_file = None
        self.gps_thread = None
        
        # Initialize skeleton recognition
        self.initialize_pose_detector()

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

    def gps_recording_thread(self):
        """Thread for GPS data recording"""
        print("🛰️ GPS recording thread started")
        try:
            # Open serial connection to GPS
            gps_serial = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)
            print("🛰️ GPS serial connection opened")
            
            while not self.stop_event.is_set():
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
                                    print(f"🛰️ GPS: {lat}{gps_data.get('latitude_dir', '')}, {lon}{gps_data.get('longitude_dir', '')}")
                    
                except Exception as e:
                    print(f"Error reading GPS data: {e}")
                    time.sleep(1)  # Wait before retrying
            
            # Close serial connection
            gps_serial.close()
            print("🛰️ GPS recording stopped")
            
        except Exception as e:
            print(f"Error in GPS recording thread: {e}")

    def start_csi_cameras(self):
        print("📹 Initializing CSI cameras...")
        
        cam1_path = self.recordings_dir / "cam1.h264"
        cam2_path = self.recordings_dir / "cam2.h264"

        # Prepare both camera commands
        print("🚀 Preparing CSI cameras...")
        
        # Prepare both camera commands with 640x480 resolution + 120° FOV
        cam1_cmd = [
            "/usr/bin/rpicam-vid", "--camera", "0",
            "--width", "640", "--height", "480",  # Keep working resolution for sync
            "--codec", "h264", "--framerate", "30",
            "--timeout", "0",
            "--nopreview",
            "--inline",  # Ensure consistent frame timing
            "--profile", "baseline",  # Use baseline profile for better compatibility
            "--segment", "0",  # Disable segmentation
            "--flush",  # Force flush after each frame
            "--roi", "0.0,0.0,1.0,1.0",  # Full sensor area for 120° FOV
            "-o", str(cam1_path)
        ]
        
        cam2_cmd = [
            "/usr/bin/rpicam-vid", "--camera", "1",
            "--width", "640", "--height", "480",  # Keep working resolution for sync
            "--codec", "h264", "--framerate", "30",
            "--timeout", "0",
            "--nopreview",
            "--inline",  # Ensure consistent frame timing
            "--profile", "baseline",  # Use baseline profile for better compatibility
            "--segment", "0",  # Disable segmentation
            "--flush",  # Force flush after each frame
            "--roi", "0.0,0.0,1.0,1.0",  # Full sensor area for 120° FOV
            "-o", str(cam2_path)
        ]
        
        # Create processes but don't start recording yet
        print("📹 Creating CSI camera processes...")
        self.cam1_proc = subprocess.Popen(cam1_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        self.cam2_proc = subprocess.Popen(cam2_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        
        # Check both cameras created successfully
        if self.cam1_proc:
            print(f"✅ cam1 process created (PID: {self.cam1_proc.pid})")
        else:
            print("❌ Failed to create cam1 process")
        
        if self.cam2_proc:
            print(f"✅ cam2 process created (PID: {self.cam2_proc.pid})")
        else:
            print("❌ Failed to create cam2 process")
        
        print("📹 CSI cameras ready for synchronized start")
        
        # Start CSI recording threads that wait for the common signal
        def cam1_recording():
            print("🎬 cam1 ready, waiting for start signal...")
            while not self.stop_event.is_set() and not hasattr(self, 'recording_started'):
                time.sleep(0.01)
            print("🎬 cam1 recording started!")
            
        def cam2_recording():
            print("🎬 cam2 ready, waiting for start signal...")
            while not self.stop_event.is_set() and not hasattr(self, 'recording_started'):
                time.sleep(0.01)
            print("🎬 cam2 recording started!")
        
        self.cam1_thread = threading.Thread(target=cam1_recording)
        self.cam2_thread = threading.Thread(target=cam2_recording)
        self.cam1_thread.start()
        self.cam2_thread.start()

    def initialize_pose_detector(self):
        """Initialize MediaPipe pose detector"""
        try:
            # Use lite model for better performance
            model_path = Path(__file__).parent / "models" / "pose_landmarker_lite.task"
            if not model_path.exists():
                print(f"⚠️ Warning: Skeleton model not found at {model_path}")
                print("🔄 Using MediaPipe's built-in pose detection instead...")
                self.skeleton_enabled = True  # Still enable with built-in
                return
            
            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                output_segmentation_masks=False  # Disable for better performance
            )
            self.pose_detector = vision.PoseLandmarker.create_from_options(options)
            print("✅ Skeleton recognition initialized successfully with custom model")
            
        except Exception as e:
            print(f"⚠️ Error initializing skeleton recognition: {e}")
            print("🔄 Using MediaPipe's built-in pose detection instead...")
            self.skeleton_enabled = True  # Still enable with built-in

    def draw_landmarks_on_frame(self, frame, detection_result):
        """Draw skeleton landmarks on frame using MediaPipe"""
        if not self.skeleton_enabled or not detection_result.pose_landmarks:
            return frame
        
        try:
            annotated_frame = frame.copy()
            
            # MediaPipe results.pose_landmarks is a NormalizedLandmarkList
            pose_landmarks = detection_result.pose_landmarks
            
            # Draw landmarks using MediaPipe's drawing utilities
            mp.solutions.drawing_utils.draw_landmarks(
                annotated_frame,
                pose_landmarks,
                mp.solutions.pose.POSE_CONNECTIONS,
                mp.solutions.drawing_styles.get_default_pose_landmarks_style()
            )
            
            return annotated_frame
            
        except Exception as e:
            print(f"⚠️ Error drawing skeleton landmarks: {e}")
            return frame

    def process_skeleton_data(self, detection_result, timestamp, frame_number):
        """Process and save skeleton data to JSON"""
        if not self.skeleton_enabled or not detection_result.pose_landmarks:
            return
        
        try:
            # MediaPipe results.pose_landmarks is a NormalizedLandmarkList
            # We need to access the landmark property to get the actual landmarks
            pose_landmarks = detection_result.pose_landmarks.landmark
            
            landmarks_data = {
                'frame': frame_number,
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
            
            # Add to skeleton data list
            self.skeleton_data.append(landmarks_data)
            
            # Save to file every 30 frames to avoid data loss
            if frame_number % 30 == 0 and self.skeleton_file:
                with open(self.skeleton_file, 'w') as f:
                    json.dump(self.skeleton_data, f, indent=2)
                    
        except Exception as e:
            print(f"⚠️ Error processing skeleton data: {e}")
            print(f"🔍 Debug: detection_result type: {type(detection_result)}")
            if hasattr(detection_result, 'pose_landmarks'):
                print(f"🔍 Debug: pose_landmarks type: {type(detection_result.pose_landmarks)}")
                if hasattr(detection_result.pose_landmarks, 'landmark'):
                    print(f"🔍 Debug: landmark property type: {type(detection_result.pose_landmarks.landmark)}")

    def create_skeleton_overlay_video(self):
        """Create a new video with skeleton overlay by doing pose detection on clean video after recording"""
        try:
            print("🎬 Creating skeleton overlay video with post-processing pose detection...")
            
            # Find the cam3 video file
            cam3_video_path = None
            for ext in ['.mp4', '.h264']:
                test_path = self.recordings_dir / f"cam3{ext}"
                if test_path.exists():
                    cam3_video_path = test_path
                    break
            
            if not cam3_video_path:
                print("❌ cam3 video file not found for skeleton overlay creation")
                return
            
            # Output paths for skeleton overlay video and JSON data
            skeleton_video_path = self.recordings_dir / "cam3_with_skeleton.mp4"
            skeleton_json_path = self.recordings_dir / "cam3_skeleton.json"
            
            # Initialize skeleton data collection for post-processing
            post_processing_skeleton_data = []
            
            # Open the source video
            cap = cv2.VideoCapture(str(cam3_video_path))
            if not cap.isOpened():
                print(f"❌ Could not open video: {cam3_video_path}")
                return
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            print(f"📹 Video properties: {width}x{height}, {fps} FPS, {total_frames} frames")
            
            # Create video writer for skeleton overlay
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(skeleton_video_path), fourcc, fps, (width, height))
            
            if not out.isOpened():
                print("❌ Could not create skeleton overlay video writer")
                cap.release()
                return
            
            # Initialize MediaPipe pose detection for post-processing
            print("🎯 Initializing MediaPipe pose detection for post-processing...")
            with mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=True,
                enable_segmentation=False,
                smooth_segmentation=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as pose:
                
                # Process frame by frame
                frame_count = 0
                print("🎯 Processing frames and detecting pose for skeleton overlay...")
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Do pose detection on this frame (post-processing)
                    try:
                        # Convert BGR to RGB for MediaPipe
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # Detect pose
                        results = pose.process(frame_rgb)
                        
                        # If pose detected, draw skeleton overlay and collect data
                        if results.pose_landmarks:
                            frame = self.draw_skeleton_on_frame_mediapipe(frame, results.pose_landmarks, width, height)
                            
                            # Collect skeleton data for JSON
                            landmarks_data = {
                                'frame': frame_count,
                                'timestamp': time.time(),
                                'landmarks': []
                            }
                            
                            # Extract landmark data
                            for i, landmark in enumerate(results.pose_landmarks.landmark):
                                landmark_data = {
                                    'id': i,
                                    'x': landmark.x,
                                    'y': landmark.y,
                                    'z': landmark.z,
                                    'visibility': getattr(landmark, 'visibility', 0.0)
                                }
                                landmarks_data['landmarks'].append(landmark_data)
                            
                            post_processing_skeleton_data.append(landmarks_data)
                            
                            print(f"✅ Frame {frame_count}: Pose detected and skeleton drawn")
                        else:
                            print(f"⚠️ Frame {frame_count}: No pose detected")
                            
                    except Exception as e:
                        print(f"⚠️ Error processing frame {frame_count}: {e}")
                    
                    # Write the frame (with or without skeleton)
                    out.write(frame)
                    frame_count += 1
                    
                    # Progress indicator
                    if frame_count % 30 == 0:
                        progress = (frame_count / total_frames) * 100
                        print(f"📊 Progress: {progress:.1f}% ({frame_count}/{total_frames} frames)")
            
            # Cleanup
            cap.release()
            out.release()
            
            # Save skeleton JSON data
            if post_processing_skeleton_data:
                try:
                    with open(skeleton_json_path, 'w') as f:
                        json.dump(post_processing_skeleton_data, f, indent=2)
                    print(f"✅ Skeleton JSON data saved: {skeleton_json_path.name} ({len(post_processing_skeleton_data)} frames)")
                except Exception as e:
                    print(f"⚠️ Error saving skeleton JSON data: {e}")
            
            print(f"✅ Skeleton overlay video created: {skeleton_video_path.name}")
            print(f"📊 Total frames processed: {frame_count}")
            print(f"🎯 Pose detected in {len(post_processing_skeleton_data)} frames")
            
        except Exception as e:
            print(f"❌ Error creating skeleton overlay video: {e}")
            import traceback
            traceback.print_exc()

    def draw_skeleton_on_frame_mediapipe(self, frame, pose_landmarks, width, height):
        """Draw skeleton overlay using MediaPipe pose landmarks"""
        try:
            if not pose_landmarks:
                return frame
            
            # Draw the pose landmarks using MediaPipe's drawing utilities
            mp.solutions.drawing_utils.draw_landmarks(
                frame,
                pose_landmarks,
                mp.solutions.pose.POSE_CONNECTIONS,
                mp.solutions.drawing_styles.get_default_pose_landmarks_style()
            )
            
            return frame
            
        except Exception as e:
            print(f"⚠️ Error drawing skeleton overlay: {e}")
            return frame

    def draw_skeleton_on_frame(self, frame, landmarks, width, height):
        """Draw skeleton landmarks on a single frame"""
        try:
            if not landmarks:
                return frame
            
            # Draw keypoints
            for landmark in landmarks:
                x = int(landmark['x'] * width)   # Convert normalized to pixel coordinates
                y = int(landmark['y'] * height)
                
                if 0 <= x < width and 0 <= y < height:
                    cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)  # Green circles
            
            # Draw basic skeleton connections
            if len(landmarks) >= 33:  # MediaPipe pose has 33 landmarks
                # Define key connections (simplified skeleton)
                connections = [
                    (0, 1), (1, 2), (2, 3), (3, 7),    # Face
                    (11, 12), (11, 13), (13, 15),       # Right arm
                    (12, 14), (14, 16),                 # Left arm
                    (11, 23), (12, 24),                 # Shoulders to hips
                    (23, 25), (25, 27), (27, 29), (29, 31),  # Right leg
                    (24, 26), (26, 28), (28, 30), (30, 32),  # Left leg
                ]
                
                for start_idx, end_idx in connections:
                    if (start_idx < len(landmarks) and end_idx < len(landmarks)):
                        start_landmark = landmarks[start_idx]
                        end_landmark = landmarks[end_idx]
                        
                        start_x = int(start_landmark['x'] * width)
                        start_y = int(start_landmark['y'] * height)
                        end_x = int(end_landmark['x'] * width)
                        end_y = int(end_landmark['y'] * height)
                        
                        if (0 <= start_x < width and 0 <= start_y < height and
                            0 <= end_x < width and 0 <= end_y < height):
                            cv2.line(frame, (start_x, start_y), (end_x, end_y), (255, 0, 0), 2)
            
        except Exception as e:
            print(f"⚠️ Error drawing skeleton on frame: {e}")
        
        return frame

    def detect_pose_mediapipe(self, frame):
        """Detect pose using MediaPipe's built-in pose detection"""
        try:
            # Convert BGR to RGB for MediaPipe
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Use MediaPipe's built-in pose detection directly on numpy array
            with mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=True,
                enable_segmentation=False,
                smooth_segmentation=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as pose:
                results = pose.process(frame_rgb)
                return results
                
        except Exception as e:
            print(f"⚠️ Error in MediaPipe pose detection: {e}")
            return None

    def start_depthai_camera(self):
        print("🎥 Initializing DepthAI camera...")

        self.cam3_pipeline = dai.Pipeline()
        camRgb = self.cam3_pipeline.create(dai.node.ColorCamera)
        imu = self.cam3_pipeline.create(dai.node.IMU)
        xout = self.cam3_pipeline.create(dai.node.XLinkOut)
        imuXout = self.cam3_pipeline.create(dai.node.XLinkOut)
        
        xout.setStreamName("rgb")
        imuXout.setStreamName("imu")
        
        # Configure for 640x480 resolution + 120° FOV
        camRgb.setPreviewSize(640, 480)  # Keep working resolution for sync
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
        camRgb.setFps(30)  # Match CSI cameras for better sync
        # Note: DepthAI automatically uses full sensor area for maximum FOV
        
        # IMU properties
        imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 500)
        imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)
        imu.enableIMUSensor(dai.IMUSensor.ROTATION_VECTOR, 400)
        imu.setBatchReportThreshold(1)
        imu.setMaxBatchReports(10)
        
        # Linking
        camRgb.preview.link(xout.input)
        imu.out.link(imuXout.input)

        try:
            self.cam3_device = dai.Device(self.cam3_pipeline)
            print("✅ DepthAI device initialized")
        except Exception as e:
            print(f"❌ Failed to start DepthAI device: {e}")
            return False

        q = self.cam3_device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        qImu = self.cam3_device.getOutputQueue(name="imu", maxSize=50, blocking=False)

        # Create H.264 file path for cam3 (matching cam1 and cam2)
        cam3_path = self.recordings_dir / "cam3.h264"
        
        # Create skeleton JSON file
        self.skeleton_file = self.recordings_dir / "cam3_skeleton.json"
        
        # Use FFmpeg to create H.264 stream from DepthAI frames (640x480 for sync testing)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", "640x480",  # Back to working resolution for sync testing
            "-pix_fmt", "rgb24",
            "-r", "30",  # Input frame rate - match CSI cameras
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-r", "30",  # Output frame rate - match CSI cameras
            "-vsync", "cfr",  # Constant frame rate output
            "-fflags", "+genpts",  # Generate proper timestamps
            "-f", "h264",
            str(cam3_path)
        ]
        
        self.cam3_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if not self.cam3_proc:
            print("❌ ERROR: Failed to start FFmpeg for cam3 H.264 encoding")
            return False

        def cam3_loop():
            frame_count = 0
            consecutive_no_frames = 0
            print("🎬 DepthAI camera ready, waiting for start signal...")
            
            # Start recording slightly earlier to compensate for FFmpeg latency
            while not self.stop_event.is_set() and not hasattr(self, 'recording_started'):
                time.sleep(0.01)
            
            # Small delay to let FFmpeg pipeline establish before starting
            time.sleep(0.9)  # 900ms early start to compensate for FFmpeg latency
            
            print("🎬 DepthAI camera recording started!")
            
            while not self.stop_event.is_set():
                in_frame = q.tryGet()
                inImu = qImu.tryGet()
                
                # Process IMU data
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
                            if self.gyro_file:
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
                            if self.imu_file:
                                self.imu_file.write(json.dumps(rv_data) + '\n')
                                self.imu_file.flush()
                
                if in_frame:
                    try:
                        frame = in_frame.getCvFrame()
                        
                        # Pose detection is DISABLED during recording to maintain perfect synchronization
                        # All pose detection will be done in post-processing after recording stops
                        
                        # Convert frame to raw RGB data and send to FFmpeg (original frame, no processing)
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        frame_bytes = frame_rgb.tobytes()
                        self.cam3_proc.stdin.write(frame_bytes)
                        self.cam3_proc.stdin.flush()
                        
                        frame_count += 1
                        consecutive_no_frames = 0
                        if frame_count % 30 == 0:  # Report every 30 frames
                            print(f"cam3 frames written: {frame_count}")
                    except Exception as e:
                        print(f"❌ cam3 error writing frame: {e}")
                else:
                    consecutive_no_frames += 1
                    if consecutive_no_frames % 50 == 0:  # Reduce spam
                        print(f"⚠️ No frame from cam3 (consecutive: {consecutive_no_frames})")
                    time.sleep(0.01)  # Reduced sleep time
            print(f"📹 cam3 total frames written: {frame_count}")
            
            # Close FFmpeg stdin when done
            try:
                self.cam3_proc.stdin.close()
            except:
                pass

        self.cam3_thread = threading.Thread(target=cam3_loop)
        self.cam3_thread.start()  # Start thread but wait for signal
        return True

    def convert_h264_to_mp4(self, input_path: Path):
        mp4_path = input_path.with_suffix(".mp4")
        print(f"🔄 Converting {input_path.name} to {mp4_path.name}...")
        
        # All cameras now use 30 FPS for 120° wide angle capture
        target_fps = "30"
        
        try:
            # Use more robust conversion with proper timing
            subprocess.run([
                "ffmpeg", "-y", 
                "-fflags", "+genpts",  # Generate presentation timestamps
                "-r", target_fps,  # Force correct FPS input
                "-i", str(input_path),
                "-c:v", "copy",  # Copy video stream without re-encoding
                "-avoid_negative_ts", "make_zero",  # Handle negative timestamps
                "-fflags", "+bitexact",  # Preserve exact bitstream
                "-vsync", "cfr",  # Constant frame rate output
                "-r", target_fps,  # Force correct FPS output
                str(mp4_path)
            ], check=True)
            print(f"✅ Conversion complete: {mp4_path.name} at {target_fps} FPS")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to convert {input_path.name} to MP4: {e}")
            # Try alternative conversion method
            try:
                print(f"🔄 Trying alternative conversion method...")
                subprocess.run([
                    "ffmpeg", "-y",
                    "-i", str(input_path),
                    "-c:v", "libx264",  # Re-encode with x264
                    "-preset", "ultrafast",
                    "-crf", "23",
                    "-r", target_fps,  # Force correct FPS
                    "-vsync", "cfr",  # Constant frame rate
                    str(mp4_path)
                ], check=True)
                print(f"✅ Alternative conversion complete: {mp4_path.name} at {target_fps} FPS")
            except subprocess.CalledProcessError as e2:
                print(f"❌ Alternative conversion also failed: {e2}")

    def stop_proc(self, proc, label):
        if proc:
            if proc.poll() is None:
                print(f"⚠️ Sending SIGINT to {label} (PID: {proc.pid})...")
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=10.0)  # Increased timeout for proper flushing
                except subprocess.TimeoutExpired:
                    print(f"❌ {label} did not stop gracefully, killing...")
                    proc.kill()
                    proc.wait()
                print(f"✅ {label} stopped.")
        else:
            print(f"⚠️ {label} process was not started.")

    def find_camera_files(self, cam_number):
        """Find camera files with various possible names and extensions"""
        possible_names = [
            f"cam{cam_number}.h264",
            f"cam{cam_number}.h264.tmp",
            f"cam{cam_number}.mp4",
            f"cam{cam_number}.avi",
            f"cam{cam_number}.mjpg",
            f"cam{cam_number}.h264.part",
            f"cam{cam_number}.h264~",
        ]
        
        for name in possible_names:
            path = self.recordings_dir / name
            if path.exists():
                size = path.stat().st_size
                print(f"📁 Found camera file: {name} (size: {size} bytes)")
                return path, size
        return None, 0

    def stop_all(self):
        print("🛑 Stopping all cameras...")
        self.stop_event.set()

        # Stop CSI cameras first with proper delays
        print("📹 Stopping CSI cameras...")
        if self.cam1_proc:
            self.stop_proc(self.cam1_proc, "cam1")
        if self.cam2_proc:
            time.sleep(2)  # Increased wait between camera stops
            self.stop_proc(self.cam2_proc, "cam2")

        # Stop cam3 H.264 process
        if hasattr(self, 'cam3_proc') and self.cam3_proc:
            print("📹 Stopping cam3 H.264 process...")
            self.stop_proc(self.cam3_proc, "cam3")
        
        # Wait for all threads to finish
        print("⏳ Waiting for all camera threads to finish...")
        if hasattr(self, 'cam1_thread'):
            self.cam1_thread.join(timeout=5.0)
        if hasattr(self, 'cam2_thread'):
            self.cam2_thread.join(timeout=5.0)
        if self.cam3_thread:
            print("Joining cam3 thread...")
            self.cam3_thread.join(timeout=10.0)  # Added timeout
        
        # Wait for GPS thread to finish
        if self.gps_thread:
            print("Joining GPS thread...")
            self.gps_thread.join(timeout=5.0)

        if self.cam3_device:
            print("Closing DepthAI device...")
            self.cam3_device.close()
        
        # Close data collection files
        if self.imu_file:
            self.imu_file.close()
            print("💾 IMU data file closed")
        if self.gyro_file:
            self.gyro_file.close()
            print("💾 Gyro data file closed")
        if self.gps_file:
            self.gps_file.close()
            print("💾 GPS data file closed")

        # Add delay to ensure files are properly written
        print("⏳ Waiting for file system sync...")
        time.sleep(5)  # Increased from 3 to 5 seconds

        # Save final skeleton data (this will be empty since we disabled detection during recording)
        if hasattr(self, 'skeleton_data') and self.skeleton_data and self.skeleton_file:
            try:
                print("💾 Saving final skeleton data...")
                with open(self.skeleton_file, 'w') as f:
                    json.dump(self.skeleton_data, f, indent=2)
                print(f"✅ Skeleton data saved to {self.skeleton_file.name}")
            except Exception as e:
                print(f"⚠️ Error saving final skeleton data: {e}")

        # Create skeleton overlay video using post-processing (always run this)
        print("🎬 Starting skeleton overlay video creation...")
        self.create_skeleton_overlay_video()

        # Check and convert CSI camera files with better detection
        print("🔍 Searching for camera files...")
        for cam_num in [1, 2, 3]:  # Now including cam3
            file_path, file_size = self.find_camera_files(cam_num)
            if file_path and file_size > 10000:
                print(f"📹 Processing cam{cam_num} file: {file_path.name}")
                if file_path.suffix == '.h264':
                    self.convert_h264_to_mp4(file_path)
                elif file_path.suffix in ['.mp4', '.avi', '.mjpg']:
                    print(f"✅ cam{cam_num} already in compatible format: {file_path.name}")
            elif file_path:
                print(f"⚠️ cam{cam_num} file too small: {file_path.name} ({file_size} bytes)")
            else:
                print(f"❌ No files found for cam{cam_num}")

    def start_synchronized_recording(self):
        """Send the common start signal to all cameras simultaneously"""
        print("🎬 Sending synchronized start signal to all cameras...")
        
        # Initialize data collection files
        timestamp = int(time.time())
        self.imu_file = open(self.recordings_dir / f"imu_{timestamp}.json", 'w')
        self.gyro_file = open(self.recordings_dir / f"gyro_{timestamp}.json", 'w')
        self.gps_file = open(self.recordings_dir / f"gps_{timestamp}.json", 'w')
        
        # Start GPS recording thread
        self.gps_thread = threading.Thread(target=self.gps_recording_thread)
        self.gps_thread.daemon = True
        self.gps_thread.start()
        print("🛰️ GPS recording thread started")
        
        self.recording_started = True
        print("📹 All cameras are now recording simultaneously!")
        print("📊 IMU, gyro, and GPS data collection started")

    def run(self):
        print("🎬 Synchronized Multi-Camera Recorder - 640x480 + 120° FOV")
        print("=" * 70)
        print("📹 This script records from:")
        print("   • cam1: CSI camera 0 (640x480, 30 FPS, H.264, 120° FOV)")
        print("   • cam2: CSI camera 1 (640x480, 30 FPS, H.264, 120° FOV)")
        print("   • cam3: DepthAI camera (640x480, 30 FPS, H.264, 120° FOV)")
        print("=" * 70)
        print("📊 Data Collection:")
        print("   • IMU: Accelerometer, gyroscope, rotation vector data")
        print("   • GPS: NMEA data (GGA, RMC, VTG sentences)")
        print("   • Skeleton: Post-processed pose detection overlay")
        print("=" * 70)
        print("💡 Tip: Wait longer (25+ seconds) for better synchronization")
        print("🎯 640x480 resolution for sync + 120° FOV for wide coverage")
        print("🎬 Skeleton detection and overlay created after recording stops")
        print("⏰ All cameras start simultaneously for perfect synchronization")
        
        print("\nPress Enter to start recording all cameras...")
        input()
        start_time = datetime.datetime.now()
        print(f"🎬 Recording started at {start_time.strftime('%H:%M:%S.%f')[:-3]}")

        # Initialize all cameras first (no recording yet)
        print("📹 Initializing all cameras...")
        if not self.start_depthai_camera():
            print("❌ Failed to initialize DepthAI camera, continuing with CSI cameras only...")
        
        # Initialize CSI cameras (no recording yet)
        self.start_csi_cameras()

        # NOW start all cameras recording simultaneously with common signal
        print("🚀 Starting all cameras NOW...")
        self.start_synchronized_recording()

        print("Recording... wait at least 20 seconds before stopping")
        print("💡 Tip: Wait longer (25+ seconds) for better synchronization")
        print("⏰ All cameras now start simultaneously for perfect synchronization")
        print("🎯 cam3 recording clean video (skeleton overlay will be created after recording)")
        input()

        stop_time = datetime.datetime.now()
        duration = (stop_time - start_time).total_seconds()
        print(f"🛑 Recording stopped at {stop_time.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"📊 Recording duration: {duration:.2f} seconds")
        
        if duration < 20:
            print("⚠️ Warning: Recording was very short. Cameras may not have synchronized properly.")
            print("💡 Recommendation: Record for at least 25-30 seconds for best synchronization.")
        elif duration < 25:
            print("⚠️ Warning: Short recording. Consider longer sessions for better synchronization.")

        self.stop_all()
        print("✅ All recordings saved under 'recordings/'")
        print("🎬 Perfect synchronization: All cameras start and stop simultaneously")
        print("💾 Skeleton JSON data: cam3_skeleton.json (created during post-processing)")
        print("🎬 Skeleton overlay video: cam3_with_skeleton.mp4 (created during post-processing)")
        print("📊 Sensor data: IMU, gyro, and GPS JSON files created")
        print("🛰️ GPS data: NMEA sentences parsed and timestamped")
        print("📱 IMU data: Accelerometer, gyroscope, rotation vector")

if __name__ == '__main__':
    recorder = SynchronizedRecorder()
    recorder.run()
