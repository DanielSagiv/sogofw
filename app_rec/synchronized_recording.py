#!/usr/bin/env python3
"""
Synchronized Multi-Camera Recording System
Samples frames from all cameras simultaneously every 0.5 seconds using Raspberry Pi OS clock
Creates synchronized videos upon user request
"""

import cv2
import depthai as dai
import threading
import time
import datetime
import subprocess
import pathlib
import sys
import os
from pathlib import Path
from collections import deque
import numpy as np

try:
    from grove_lcd_rgb import set_text, set_rgb
    LCD_AVAILABLE = True
except Exception:
    LCD_AVAILABLE = False
    def set_text(text): pass
    def set_rgb(r, g, b): pass

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

class SynchronizedRecorder:
    def __init__(self):
        self.recordings_dir = Path("recordings")
        self.recordings_dir.mkdir(exist_ok=True)
        self.camera_frames = {"cam1": deque(), "cam2": deque(), "cam3": deque()}
        self.frame_locks = {"cam1": threading.Lock(), "cam2": threading.Lock(), "cam3": threading.Lock()}
        self.camera_threads = {}
        self.sampling_active = False
        self.stop_event = threading.Event()
        self.sample_event = threading.Event()
        self.sample_interval = 0.5
        self.next_sample_time = 0
        if LCD_AVAILABLE:
            set_rgb(0, 128, 64)
            set_text("READY")

    def initialize_sampling_time(self):
        current_time = time.time()
        self.next_sample_time = ((current_time // self.sample_interval) + 1) * self.sample_interval

    def start_sampling_timer(self):
        def timer_thread():
            while self.sampling_active and not self.stop_event.is_set():
                current_time = time.time()
                if current_time >= self.next_sample_time:
                    self.sample_event.set()
                    self.next_sample_time += self.sample_interval
                    time.sleep(0.3)
                    self.sample_event.clear()
                else:
                    time.sleep(0.01)
        t = threading.Thread(target=timer_thread)
        t.daemon = True
        t.start()

    def camera_thread(self, cam_id, device_index):
        cap = cv2.VideoCapture(device_index)
        while not self.stop_event.is_set():
            if self.sample_event.wait(timeout=0.1):
                ret, frame = cap.read()
                if ret:
                    with self.frame_locks[cam_id]:
                        self.camera_frames[cam_id].append((frame.copy(), time.time()))
            time.sleep(0.01)
        cap.release()

    def depthai_thread(self):
        pipeline = dai.Pipeline()
        camRgb = pipeline.create(dai.node.ColorCamera)
        xout = pipeline.create(dai.node.XLinkOut)
        xout.setStreamName("rgb")
        camRgb.setPreviewSize(640, 480)
        camRgb.setInterleaved(False)
        camRgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.RGB)
        camRgb.preview.link(xout.input)
        with dai.Device(pipeline) as device:
            q = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            while not self.stop_event.is_set():
                if self.sample_event.wait(timeout=0.1):
                    inRgb = q.tryGet()
                    if inRgb:
                        frame = inRgb.getCvFrame()
                        with self.frame_locks["cam3"]:
                            self.camera_frames["cam3"].append((frame.copy(), time.time()))
                time.sleep(0.01)

    def start_camera_threads(self):
        self.camera_threads["cam1"] = threading.Thread(target=self.camera_thread, args=("cam1", 0))
        self.camera_threads["cam2"] = threading.Thread(target=self.camera_thread, args=("cam2", 1))
        self.camera_threads["cam3"] = threading.Thread(target=self.depthai_thread)
        for t in self.camera_threads.values():
            t.daemon = True
            t.start()

    def start_sampling(self):
        self.initialize_sampling_time()
        self.sampling_active = True
        self.start_sampling_timer()

    def stop_sampling(self):
        self.sampling_active = False
        self.stop_event.set()
        for t in self.camera_threads.values():
            t.join(timeout=2.0)
        self.create_videos()

    def create_videos(self):
        for cam_id in ["cam1", "cam2", "cam3"]:
            frames = self.camera_frames[cam_id]
            if not frames:
                continue
            filename = self.recordings_dir / f"{cam_id}_{int(time.time())}.mp4"
            h, w = frames[0][0].shape[:2]
            out = cv2.VideoWriter(str(filename), cv2.VideoWriter_fourcc(*'mp4v'), 2.0, (w, h))
            for frame, _ in frames:
                out.write(frame)
            out.release()

    def cleanup(self):
        self.stop_event.set()

    def run(self):
        print("Press Enter to start sampling")
        input()
        self.start_camera_threads()
        self.start_sampling()
        print("Sampling started. Press Enter to stop and save videos")
        input()
        self.stop_sampling()
        if LCD_AVAILABLE:
            set_rgb(0, 128, 64)
            set_text("SOGO READY")

def main():
    recorder = SynchronizedRecorder()
    recorder.run()

if __name__ == "__main__":
    main()
