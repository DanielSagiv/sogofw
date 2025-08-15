#!/usr/bin/env python3
import cv2
import depthai as dai
import subprocess
import threading
import time
import os
import signal
import numpy as np
from collections import deque

# Preview settings
WIDTH, HEIGHT, FPS = 640, 480, 30
WINDOW_NAMES = ["CSI Cam 0", "CSI Cam 1", "DepthAI Cam"]

# Frame storage for each camera
camera_frames = {
    "CSI Cam 0": deque(),
    "CSI Cam 1": deque(), 
    "DepthAI Cam": deque()
}

# Global flags
sampling_active = False
cameras_ready = False

def start_rpicam_preview(index, name):
    cmd = [
        "rpicam-vid",
        "--camera", str(index),
        "--width", str(WIDTH),
        "--height", str(HEIGHT),
        "--framerate", str(FPS),
        "--preview", "-",
        "--nopreview", "0",
        "--fullscreen", "0",
        "--info-text", name,
        "-t", "0",
    ]
    return subprocess.Popen(cmd, preexec_fn=os.setsid)

def start_depthai_preview(name):
    def run():
        pipeline = dai.Pipeline()
        cam = pipeline.create(dai.node.ColorCamera)
        cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setVideoSize(WIDTH, HEIGHT)
        cam.setFps(FPS)

        xout = pipeline.create(dai.node.XLinkOut)
        xout.setStreamName("video")
        cam.video.link(xout.input)

        device = dai.Device(pipeline)
        q = device.getOutputQueue("video", maxSize=4, blocking=False)

        global cameras_ready
        cameras_ready = True

        while True:
            frame = q.get().getCvFrame()
            cv2.imshow(name, frame)
            
            # Sample frame if sampling is active
            if sampling_active:
                camera_frames[name].append(frame.copy())
                print(f"[SAMPLING] {name}: {len(camera_frames[name])} frames")
            
            if cv2.waitKey(1) == 27:  # Esc to close
                break

        cv2.destroyWindow(name)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

def sample_frames():
    global sampling_active
    print("[INFO] Starting frame sampling from all cameras...")
    sampling_active = True
    
    input("[READY] Sampling active. Press ENTER to stop sampling and create videos...")
    
    sampling_active = False
    print("[INFO] Stopping frame sampling...")
    
    # Create videos from sampled frames
    create_videos_from_samples()

def create_videos_from_samples():
    print("[INFO] Creating videos from sampled frames...")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    
    for camera_name, frames in camera_frames.items():
        if len(frames) == 0:
            print(f"[WARNING] No frames captured for {camera_name}")
            continue
            
        # Create video filename
        video_filename = f"{camera_name.replace(' ', '_').lower()}_sample.mp4"
        
        # Get frame dimensions from first frame
        first_frame = frames[0]
        height, width = first_frame.shape[:2]
        
        # Create video writer
        out = cv2.VideoWriter(video_filename, fourcc, FPS, (width, height))
        
        print(f"[PROCESSING] Creating video for {camera_name}: {len(frames)} frames")
        
        # Write all frames to video
        for frame in frames:
            out.write(frame)
        
        out.release()
        print(f"[SUCCESS] Video saved: {video_filename}")
    
    print("[DONE] All videos created successfully!")

def main():
    print("[INFO] Launching all 3 camera previews...")

    # Start CSI previews via rpicam-vid
    p0 = start_rpicam_preview(0, "CSI Cam 0")
    p1 = start_rpicam_preview(1, "CSI Cam 1")

    # Start DepthAI preview in a thread
    oak_thread = start_depthai_preview("DepthAI Cam")

    # Wait for cameras to be ready
    while not cameras_ready:
        time.sleep(0.1)

    input("[READY] All cameras live. Press ENTER to begin frame sampling...")

    # Start frame sampling
    sample_frames()

    # Cleanup CSI camera previews
    for p in [p0, p1]:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGINT)
        except Exception:
            pass

    print("[DONE] Exiting.")

if __name__ == "__main__":
    main()
