#!/usr/bin/env python3
import cv2
import depthai as dai
import subprocess
import threading
import time
import os
import signal
from datetime import datetime
from collections import deque

# Config
WIDTH, HEIGHT, FPS = 640, 480, 30
SAMPLE_INTERVAL = 0.5
SESSION_ROOT = "recordings"

# Buffers for each camera
buffers = {
    "cam0": deque(),
    "cam1": deque(),
    "cam3": deque(),
}

# Sync
start_sampling = threading.Event()
stop_sampling = threading.Event()

def make_session_folder():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(SESSION_ROOT, f"session_{ts}")
    os.makedirs(folder, exist_ok=True)
    return folder

def capture_csi(index, label):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    if not cap.isOpened():
        print(f"[ERROR] Failed to open CSI camera {index} ({label})")
        return

    while not stop_sampling.is_set():
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        cv2.imshow(label, frame)
        key = cv2.waitKey(1)
        if key == 27:
            break

        if start_sampling.is_set():
            buffers[label].append(frame.copy())

        time.sleep(SAMPLE_INTERVAL)

    cap.release()
    cv2.destroyWindow(label)

def capture_oak(label="cam3"):
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

    while not stop_sampling.is_set():
        frame_packet = q.tryGet()
        if frame_packet:
            frame = frame_packet.getCvFrame()
            cv2.imshow("DepthAI Cam", frame)
            key = cv2.waitKey(1)
            if key == 27:
                break
            if start_sampling.is_set():
                buffers[label].append(frame.copy())

        time.sleep(SAMPLE_INTERVAL)

    cv2.destroyWindow("DepthAI Cam")

def write_video(frames, out_path):
    if not frames:
        print(f"[WARN] No frames to write to {out_path}")
        return
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, 1.0 / SAMPLE_INTERVAL, (WIDTH, HEIGHT))
    for f in frames:
        writer.write(f)
    writer.release()
    print(f"[OK] Saved {out_path}")

def main():
    session = make_session_folder()
    print("[INFO] Initializing all cameras...")

    # Start camera threads
    t0 = threading.Thread(target=capture_csi, args=(0, "cam0"), daemon=True)
    t1 = threading.Thread(target=capture_csi, args=(1, "cam1"), daemon=True)
    t3 = threading.Thread(target=capture_oak, args=("cam3",), daemon=True)

    t0.start()
    t1.start()
    t3.start()

    input("[READY] All cameras live. Press ENTER to start sampling every 0.5s...")
    start_sampling.set()

    input("[REC] Sampling... Press ENTER again to stop and save.")
    stop_sampling.set()

    print("[INFO] Stopping...")

    t0.join()
    t1.join()
    t3.join()

    print("[INFO] Saving all videos...")

    write_video(buffers["cam0"], os.path.join(session, "cam1.mp4"))
    write_video(buffers["cam1"], os.path.join(session, "cam2.mp4"))
    write_video(buffers["cam3"], os.path.join(session, "cam3.mp4"))

    print(f"[DONE] All videos saved in: {session}")

if __name__ == "__main__":
    main()
