""#!/usr/bin/env python3
"""
Synchronized Multi-Cam Recording (CSI1, CSI2, DepthAI) to H.264
Starts all 3 cameras together, stops on Enter, saves 3 synced files
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

class SynchronizedRecorder:
    def __init__(self):
        self.recordings_dir = Path("recordings")
        self.recordings_dir.mkdir(exist_ok=True)

        self.cam1_proc = None
        self.cam2_proc = None
        self.cam3_thread = None
        self.stop_event = threading.Event()
        self.cam3_writer = None
        self.cam3_pipeline = None
        self.cam3_device = None

    def start_csi_camera(self, cam_index: int, filename: str):
        print(f"Starting CSI camera {cam_index} recording to {filename} via ffmpeg pipe...")
        cmd_rpicam = [
            "rpicam-vid", "--camera", str(cam_index),
            "--codec", "h264", "--framerate", "30",
            "--timeout", "0", "--inline", "-o", "-"
        ]
        cmd_ffmpeg = [
            "ffmpeg", "-y", "-f", "h264", "-i", "-",
            "-c:v", "copy", str(filename)
        ]
        rpicam = subprocess.Popen(cmd_rpicam, stdout=subprocess.PIPE)
        ffmpeg = subprocess.Popen(cmd_ffmpeg, stdin=rpicam.stdout)
        return rpicam, ffmpeg

    def start_csi_cameras(self):
        cam1_path = self.recordings_dir / "cam1.h264"
        cam2_path = self.recordings_dir / "cam2.h264"

        self.cam1_proc = self.start_csi_camera(0, cam1_path)
        print(f"cam1 PID: {self.cam1_proc[0].pid}")

        self.cam2_proc = self.start_csi_camera(1, cam2_path)
        print(f"cam2 PID: {self.cam2_proc[0].pid}")

    def start_depthai_camera(self):
        print("Starting DepthAI camera recording (cam3.avi with XVID codec)...")

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

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        cam3_path = str(self.recordings_dir / "cam3.avi")
        self.cam3_writer = cv2.VideoWriter(cam3_path, fourcc, 30.0, (640, 480))

        if not self.cam3_writer.isOpened():
            print("❌ ERROR: Failed to open VideoWriter for cam3.avi. Check codec and permissions.")
            return

        def cam3_loop():
            frame_count = 0
            while not self.stop_event.is_set():
                in_frame = q.tryGet()
                if in_frame:
                    frame = in_frame.getCvFrame()
                    self.cam3_writer.write(frame)
                    frame_count += 1
                time.sleep(0.001)
            print(f"📹 cam3 total frames written: {frame_count}")

        self.cam3_thread = threading.Thread(target=cam3_loop)
        self.cam3_thread.start()

    def convert_h264_to_mp4(self, input_path: Path):
        mp4_path = input_path.with_suffix(".mp4")
        print(f"🔄 Converting {input_path.name} to {mp4_path.name}...")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-framerate", "30", "-i", str(input_path),
                "-c:v", "copy", str(mp4_path)
            ], check=True)
            print(f"✅ Conversion complete: {mp4_path.name}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to convert {input_path.name} to MP4: {e}")

    def stop_rpicam_ffmpeg(self, proc_tuple, label):
        if proc_tuple:
            rpicam_proc, ffmpeg_proc = proc_tuple
            for proc, name in [(rpicam_proc, f"{label}-rpicam"), (ffmpeg_proc, f"{label}-ffmpeg")]:
                if proc.poll() is None:
                    print(f"⚠️  Sending SIGINT to {name} (PID: {proc.pid})...")
                    proc.send_signal(signal.SIGINT)
                    try:
                        proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        print(f"❌ {name} did not stop gracefully, killing...")
                        proc.kill()
                        proc.wait()
                    print(f"✅ {name} stopped.")
        else:
            print(f"⚠️  {label} processes were not started.")

    def stop_all(self):
        print("Stopping all cameras...")
        self.stop_event.set()

        self.stop_rpicam_ffmpeg(self.cam1_proc, "cam1")
        self.stop_rpicam_ffmpeg(self.cam2_proc, "cam2")

        if self.cam3_thread:
            print("Joining cam3 thread...")
            self.cam3_thread.join()

        if self.cam3_writer:
            self.cam3_writer.release()
            print("cam3.avi saved.")

        if self.cam3_device:
            print("Closing DepthAI device...")
            self.cam3_device.close()

        for cam_file in ["cam1.h264", "cam2.h264"]:
            path = self.recordings_dir / cam_file
            if path.exists():
                size = path.stat().st_size
                print(f"📁 {cam_file} size: {size} bytes")
                if size > 1000:
                    self.convert_h264_to_mp4(path)
                else:
                    print(f"⚠️ Skipping conversion for {cam_file}: file too small")
            else:
                print(f"⚠️ {cam_file} missing, skipping")

    def run(self):
        print("Press Enter to start recording all cameras...")
        input()
        start_time = datetime.datetime.now()
        print(f"🎬 Recording started at {start_time.strftime('%H:%M:%S.%f')[:-3]}")

        self.start_depthai_camera()
        self.start_csi_cameras()

        print("Recording... wait at least 5 seconds before stopping")
        input()

        stop_time = datetime.datetime.now()
        print(f"🛑 Recording stopped at {stop_time.strftime('%H:%M:%S.%f')[:-3]}")

        self.stop_all()
        print("✅ All recordings saved under 'recordings/'")

if __name__ == '__main__':
    recorder = SynchronizedRecorder()
    recorder.run()
