import os
import subprocess
import datetime
import signal
import time

def make_fifo(path):
    if os.path.exists(path):
        os.remove(path)
    os.mkfifo(path)

def start_camera(camera_id, fifo_path):
    return subprocess.Popen([
        "rpicam-vid",
        "--camera", str(camera_id),
        "-t", "0",
        "-o", fifo_path
    ])

def start_writer(fifo_path, output_path):
    return subprocess.Popen([
        "tee", output_path
    ], stdin=open(fifo_path, 'rb'))

def main():
    input("Press ENTER to START recording...")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fifo0 = "/tmp/cam0_fifo"
    fifo1 = "/tmp/cam1_fifo"
    out0 = f"camera0_{timestamp}.h264"
    out1 = f"camera1_{timestamp}.h264"

    make_fifo(fifo0)
    make_fifo(fifo1)

    print("Starting cameras...")

    # Start camera streaming into FIFO
    cam0_proc = start_camera(0, fifo0)
    cam1_proc = start_camera(1, fifo1)

    # Start writing FIFO to real files
    writer0 = start_writer(fifo0, out0)
    writer1 = start_writer(fifo1, out1)

    input("Recording... Press ENTER to STOP.")

    print("Stopping...")

    cam0_proc.terminate()
    cam1_proc.terminate()
    cam0_proc.wait()
    cam1_proc.wait()

    writer0.terminate()
    writer1.terminate()
    writer0.wait()
    writer1.wait()

    os.remove(fifo0)
    os.remove(fifo1)

    print(f"Saved:\n - {out0}\n - {out1}")

if __name__ == "__main__":
    main()
