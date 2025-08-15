#!/usr/bin/env python3
import os
import sys
import cv2
import time
import signal
import depthai as dai
import threading
import subprocess
from datetime import datetime
from collections import deque

# Config
WIDTH, HEIGHT, FPS = 640, 480, 2  # FPS = 2 since we're sampling every 0.5s
INTERVAL_SEC = 0.5
SESSION_ROOT = "recordings"

# Shared buffers
buffers = {
    "CSI0": deque(),
    "CSI1": deque(),
    "OAK": deque()
}

stop_sampling = threading.Event()
start_sampling = threading.Event()


def make_session_folder():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SESSION_ROOT, f"session_{ts}")
    os.makedirs(path, exist_ok=True)
    return path


def start_csi_stream(index, name, buffer_key):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    def run():
        while not stop_sampling.is_set():
            ret, frame = cap.read()
            if ret:
                cv2.imshow(name, frame)
                if start_sampling.is_set():
                    buffers[buffer_key].append(frame.copy())
            key = cv2.waitKey(1)
            if key == 27:
                break
        cap.release()
        cv2.destroyWindow(name)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def start_depthai_stream(buffer_key):
    def run():
        pipeline = dai.Pipeline()
        cam = pipeline.create(dai.node.ColorCamera)
        cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setVideoSize(WIDTH, HEIGHT)
        cam.setFps(30)

        xout = pipeline.create(dai.node.XLinkOut)
        xout.setStreamName("video")
        cam.video.link(xout.input)

        device = dai.Device(pipeline)
        q = device.getOutputQueue("video", maxSize=4, blocking=False)

        while not stop_sampling.is_set():
            pkt = q.tryGet()
            if pkt is not None:
                frame = pkt.getCvFrame()
                cv2.imshow("DepthAI Cam", frame)
                if start_sampling.is_set():
                    buffers[buffer_key].append(frame.copy())
            if cv2.waitKey(1) == 27:
                break
        cv2.destroyWindow("DepthAI Cam")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def logger_thread():
    print("[INFO] Sampling started. Press ENTER again to stop and save videos.")
    while not stop_sampling.is_set():
        ts = datetime.now().isoformat()
        print(f"[{ts}] Sampled.")
        time.sleep(INTERVAL_SEC)


def write_video(frames, path):
    if not frames:
        print(f"[WARN] No frames to write for {path}")
        return
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(path, fourcc, FPS, (WIDTH, HEIGHT))
    for frame in frames:
        out.write(frame)
    out.release()
    print(f"[OK] Saved {path}")


def main():
    print("[INFO] Starting live previews...")
    session = make_session_folder()

    csi0 = start_csi_stream(0, "CSI Cam 0", "CSI0")
    csi1 = start_csi_stream(1, "CSI Cam 1", "CSI1")
    oak = start_depthai_stream("OAK")

    input("[READY] All cameras live. Press ENTER to start sampling...")

    start_sampling.set()
    log_thread = threading.Thread(target=logger_thread, daemon=True)
    log_thread.start()

    input()
    stop_sampling.set()

    print("[STOP] Stopping and saving videos...")
    log_thread.join(timeout=2)
    csi0.join(timeout=2)
    csi1.join(timeout=2)
    oak.join(timeout=2)

    # Write videos
    write_video(buffers["CSI0"], os.path.join(session, "cam1.mp4"))
    write_video(buffers["CSI1"], os.path.join(session, "cam2.mp4"))
    write_video(buffers["OAK"], os.path.join(session, "cam3.mp4"))

    print(f"[DONE] All saved in: {session}")


if __name__ == "__main__":
    main()
