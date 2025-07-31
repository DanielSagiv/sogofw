import subprocess
import time
import datetime

def start_recording():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cam0_file = f"camera0_{timestamp}.h264"
    cam1_file = f"camera1_{timestamp}.h264"

    print("Starting recording... Press ENTER again to stop.\n")

    # Start both cameras
    proc_cam0 = subprocess.Popen([
        "rpicam-vid", "-t", "0", "--camera", "0", "-o", cam0_file
    ])

    proc_cam1 = subprocess.Popen([
        "rpicam-vid", "-t", "0", "--camera", "1", "-o", cam1_file
    ])

    return proc_cam0, proc_cam1, cam0_file, cam1_file

def stop_recording(proc_cam0, proc_cam1):
    proc_cam0.terminate()
    proc_cam1.terminate()
    proc_cam0.wait()
    proc_cam1.wait()
    print("Recording stopped.")

def main():
    input("Press ENTER to start recording...")
    proc_cam0, proc_cam1, file0, file1 = start_recording()
    input()
    stop_recording(proc_cam0, proc_cam1)
    print(f"Videos saved as:\n - {file0}\n - {file1}")

if __name__ == "__main__":
    main()
