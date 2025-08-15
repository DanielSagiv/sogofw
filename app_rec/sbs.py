#!/usr/bin/env python3
import cv2
import depthai as dai
import subprocess
import threading
import time
import os
import signal

# Preview settings
WIDTH, HEIGHT, FPS = 640, 480, 30
WINDOW_NAMES = ["CSI Cam 0", "CSI Cam 1", "DepthAI Cam"]

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

        while True:
            frame = q.get().getCvFrame()
            cv2.imshow(name, frame)
            if cv2.waitKey(1) == 27:  # Esc to close
                break

        cv2.destroyWindow(name)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

def log_timestamps():
    import datetime
    start = datetime.datetime.now()
    print(f"[START] {start.isoformat()}")
    try:
        while True:
            now = datetime.datetime.now()
            elapsed = (now - start).total_seconds()
            print(f"[{now.isoformat()}] +{elapsed:.2f} sec")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[STOP] Logging interrupted.")

def main():
    print("[INFO] Launching all 3 camera previews...")

    # Start CSI previews via rpicam-vid
    p0 = start_rpicam_preview(0, "CSI Cam 0")
    p1 = start_rpicam_preview(1, "CSI Cam 1")

    # Start DepthAI preview in a thread
    oak_thread = start_depthai_preview("DepthAI Cam")

    input("[READY] All cameras live. Press ENTER to begin logging timestamps...")

    # Log timestamps every 0.5 sec
    log_timestamps()

    # Cleanup CSI camera previews
    for p in [p0, p1]:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGINT)
        except Exception:
            pass

    print("[DONE] Exiting.")

if __name__ == "__main__":
    main()
