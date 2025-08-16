#!/usr/bin/env python3
"""
Synchronized Multi-Cam Recording (CSI1, CSI2, DepthAI) to H.264
Starts all 3 cameras together, stops on Enter, saves 3 .h264 files
"""

import subprocess
import threading
import time
import datetime
import cv2
import depthai as dai

class SynchronizedRecorder:
    def __init__(self):
        self.cam1_proc = None
        self.cam2_proc = None
        self.cam3_thread = None
        self.stop_event = threading.Event()
        self.cam3_writer = None
        self.cam3_pipeline = None
        self.cam3_device = None

    def start_csi_cameras(self):
        print("Starting CSI camera 1 (cam1.h264)...")
        self.cam1_proc = subprocess.Popen([
            "rpicam-vid", "--camera", "0",
            "--codec", "h264", "--framerate", "30",
            "--inline", "--timeout", "0", "-o", "cam1.h264"
        ])

        print("Starting CSI camera 2 (cam2.h264)...")
        self.cam2_proc = subprocess.Popen([
            "rpicam-vid", "--camera", "1",
            "--codec", "h264", "--framerate", "30",
            "--inline", "--timeout", "0", "-o", "cam2.h264"
        ])

    def start_depthai_camera(self):
        print("Starting DepthAI camera recording (cam3.h264)...")

        self.cam3_pipeline = dai.Pipeline()
        camRgb = self.cam3_pipeline.create(dai.node.ColorCamera)
        xout = self.cam3_pipeline.create(dai.node.XLinkOut)
        xout.setStreamName("rgb")
        camRgb.setPreviewSize(640, 480)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
        camRgb.setFps(30)
        camRgb.preview.link(xout.input)

        self.cam3_device = dai.Device(self.cam3_pipeline)
        q = self.cam3_device.getOutputQueue(name="rgb", maxSize=4, blocking=False)

        fourcc = cv2.VideoWriter_fourcc(*'H264')
        self.cam3_writer = cv2.VideoWriter("cam3.h264", fourcc, 30.0, (640, 480))

        def cam3_loop():
            while not self.stop_event.is_set():
                in_frame = q.tryGet()
                if in_frame:
                    frame = in_frame.getCvFrame()
                    self.cam3_writer.write(frame)
                time.sleep(0.001)

        self.cam3_thread = threading.Thread(target=cam3_loop)
        self.cam3_thread.start()

    def stop_all(self):
        print("Stopping all cameras...")

        self.stop_event.set()

        if self.cam1_proc:
            self.cam1_proc.terminate()
            self.cam1_proc.wait()
            print("cam1.h264 saved.")

        if self.cam2_proc:
            self.cam2_proc.terminate()
            self.cam2_proc.wait()
            print("cam2.h264 saved.")

        if self.cam3_thread:
            self.cam3_thread.join()

        if self.cam3_writer:
            self.cam3_writer.release()
            print("cam3.h264 saved.")

        if self.cam3_device:
            self.cam3_device.close()

    def run(self):
        print("Press Enter to start recording all cameras...")
        input()
        start_time = datetime.datetime.now()
        print(f"🎬 Recording started at {start_time.strftime('%H:%M:%S.%f')[:-3]}")

        self.start_csi_cameras()
        time.sleep(1.0)  # Give CSI cams 1 sec to initialize
        self.start_depthai_camera()

        print("Recording... Press Enter to stop")
        input()

        stop_time = datetime.datetime.now()
        print(f"🛑 Recording stopped at {stop_time.strftime('%H:%M:%S.%f')[:-3]}")

        self.stop_all()
        print("✅ All recordings saved.")

if __name__ == '__main__':
    recorder = SynchronizedRecorder()
    recorder.run()
