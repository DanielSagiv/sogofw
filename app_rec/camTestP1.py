import subprocess
import datetime
import signal
import time

def start_recording(camera_id, filename):
    return subprocess.Popen([
        "libcamera-vid",
        "--camera", str(camera_id),
        "-t", "600000",  # 10 minutes max
        "-o", filename,
        "--codec", "h264",
        "--profile", "high",
        "--bitrate", "4000000",
        "--nopreview"
    ])

def stop_recording(proc):
    proc.send_signal(signal.SIGINT)
    proc.wait()

def main():
    input("📷 Press ENTER to START recording...")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file0 = f"camera0_{timestamp}.h264"
    file1 = f"camera1_{timestamp}.h264"

    print("🎥 Starting...")
    proc0 = start_recording(0, file0)
    proc1 = start_recording(1, file1)

    input("🛑 Press ENTER to STOP recording...\n")

    print("⏹ Stopping...")
    stop_recording(proc0)
    stop_recording(proc1)

    print(f"✅ Saved:\n - {file0}\n - {file1}")

if __name__ == "__main__":
    main()
