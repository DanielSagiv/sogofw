#!/usr/bin/env python3
import cv2
import depthai as dai
import threading
import time
import queue
import signal
import sys

WIDTH, HEIGHT, FPS = 640, 480, 30
SAMPLE_INTERVAL = 0.5  # seconds

# Buffers
buffers = {
    "cam1": [],
    "cam2": [],
    "cam3": [],
}
stop_flag = threading.Event()

def capture_frames_from_v4l(name, device_path):
    cap = cv2.VideoCapture(device_path)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open {name} ({device_path})")
        return

    print(f"[{name}] Opened {device_path}")

    while not stop_flag.is_set():
        ret, frame = cap.read()
        if ret:
            buffers[name].append(frame.copy())
            cv2.imshow(name, frame)
        if cv2.waitKey(1) == 27:
            stop_flag.set()
            break
        time.sleep(SAMPLE_INTERVAL)

    cap.release()
    cv2.destroyWindow(name)

def capture_frames_from_depthai(name):
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

    print(f"[{name}] DepthAI stream started")

    while not stop_flag.is_set():
        frame = q.get().getCvFrame()
        if frame is not None:
            buffers[name].append(frame.copy())
            cv2.imshow(name, frame)
        if cv2.waitKey(1) == 27:
            stop_flag.set()
            break
        time.sleep(SAMPLE_INTERVAL)

    cv2.destroyWindow(name)

def save_video(name, frames):
    if not frames:
        print(f"[{name}] No frames to save")
        return
    out = cv2.VideoWriter(f"{name}.mp4", cv2.VideoWriter_fourcc(*"mp4v"), int(1/SAMPLE_INTERVAL), (WIDTH, HEIGHT))
    for f in frames:
        out.write(f)
    out.release()
    print(f"[{name}] Saved {len(frames)} frames to {name}.mp4")

def main():
    print("[INFO] Starting camera previews...")
    print("[INFO] Press ENTER once to start recording. Press ENTER again to stop.")

    # Wait for first ENTER to start
    input("[READY] Press ENTER to begin sampling...")

    # Start capture threads
    t1 = threading.Thread(target=capture_frames_from_v4l, args=("cam1", "/dev/video0"), daemon=True)
    t2 = threading.Thread(target=capture_frames_from_v4l, args=("cam2", "/dev/video8"), daemon=True)
    t3 = threading.Thread(target=capture_frames_from_depthai, args=("cam3",), daemon=True)

    for t in (t1, t2, t3):
        t.start()

    input("[RECORDING] Press ENTER again to stop sampling...")

    stop_flag.set()

    # Wait for threads to finish
    for t in (t1, t2, t3):
        t.join()

    print("[INFO] Saving all videos...")
    for name in buffers:
        save_video(name, buffers[name])

    print("[DONE] All videos saved. Exiting.")

if __name__ == "__main__":
    main()
