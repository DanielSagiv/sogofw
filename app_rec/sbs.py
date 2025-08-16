#!/usr/bin/env python3

import os
import subprocess
import threading
import time
from datetime import datetime

SESSION_DIR = f"recordings/session_{int(time.time())}"
os.makedirs(SESSION_DIR, exist_ok=True)

CAM1_PATH = os.path.join(SESSION_DIR, "cam1.h264")
CAM2_PATH = os.path.join(SESSION_DIR, "cam2.h264")
CAM3_PATH = os.path.join(SESSION_DIR, "cam3.avi")


def record_csi_camera(index, output_path):
    print(f"🎥 Starting CSI camera {index} recording to {output_path}...")
    return subprocess.Popen([
        "libcamera-vid",
        "--camera", str(index),
        "--codec", "h264",
        "-t", "0",  # infinite
        "-o", output_path,
        "--width", "640",
        "--height", "480",
        "--framerate", "30"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def convert_to_mp4(input_path, output_path):
    print(f"🔄 Converting {input_path} to {output_path}...")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", input_path,
        "-c:v", "copy",
        output_path
    ])
    print(f"✅ Conversion complete: {output_path}")


def record_cam3(output_path):
    import depthai as dai
    import cv2

    print("📹 Starting DepthAI camera recording...")
    pipeline = dai.Pipeline()
    cam_rgb = pipeline.create(dai.node.ColorCamera)
    cam_rgb.setPreviewSize(640, 480)
    cam_rgb.setInterleaved(False)
    cam_rgb.setFps(30)

    xout_video = pipeline.create(dai.node.XLinkOut)
    xout_video.setStreamName("video")
    cam_rgb.video.link(xout_video.input)

    device = dai.Device(pipeline)
    q = device.getOutputQueue(name="video", maxSize=30, blocking=True)

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(output_path, fourcc, 30.0, (640, 480))

    start_time = time.time()
    while time.time() - start_time < 15:  # record 15 seconds
        frame = q.get().getCvFrame()
        out.write(frame)

    out.release()
    device.close()
    print(f"📼 cam3 saved to {output_path}")


def main():
    input("Press Enter to start recording all cameras...")

    start_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"\n🎬 Recording started at {start_time}")

    # Start cam3 (DepthAI)
    cam3_thread = threading.Thread(target=record_cam3, args=(CAM3_PATH,))
    cam3_thread.start()

    # Start cam1 and cam2
    cam1_proc = record_csi_camera(0, CAM1_PATH)
    cam2_proc = record_csi_camera(1, CAM2_PATH)

    # Let them record
    time.sleep(15)

    # Stop cam1 and cam2
    print("🛑 Stopping CSI cameras...")
    cam1_proc.terminate()
    cam2_proc.terminate()
    cam1_proc.wait()
    cam2_proc.wait()

    # Wait for cam3 to finish
    cam3_thread.join()

    # Convert to MP4
    if os.path.exists(CAM1_PATH):
        convert_to_mp4(CAM1_PATH, CAM1_PATH.replace(".h264", ".mp4"))
    else:
        print("⚠️ cam1.h264 missing")

    if os.path.exists(CAM2_PATH):
        convert_to_mp4(CAM2_PATH, CAM2_PATH.replace(".h264", ".mp4"))
    else:
        print("⚠️ cam2.h264 missing")

    print(f"✅ All recordings saved under '{SESSION_DIR}'")


if __name__ == "__main__":
    main()
