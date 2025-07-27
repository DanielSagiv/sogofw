import sys
import os
import datetime
import argparse
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions

# Suppress TensorFlow warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# Set environment variables
os.environ["QT_QPA_PLATFORM"] = "xcb"
sys.path.append('/home/khadas/.local/lib/python3.11/site-packages')
# Get the current directory of the script
current_directory = os.path.dirname(os.path.abspath(__file__))


# Function to parse arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Record video with landmarks and segmentation masks.")
    parser.add_argument('filename', type=str, help="Output filename for the video.")
    parser.add_argument('--action', type=str, choices=['start', 'stop'], help="Action to perform")
    return parser.parse_args()

# Function to draw landmarks on the frame
def draw_landmarks_on_image(rgb_image, detection_result):
    pose_landmarks_list = detection_result.pose_landmarks
    annotated_image = np.copy(rgb_image)

    if not pose_landmarks_list:
        return annotated_image

    for pose_landmarks in pose_landmarks_list:
        pose_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
        pose_landmarks_proto.landmark.extend(
            [landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in pose_landmarks]
        )
        solutions.drawing_utils.draw_landmarks(
            annotated_image,
            pose_landmarks_proto,
            solutions.pose.POSE_CONNECTIONS,
            solutions.drawing_styles.get_default_pose_landmarks_style()
        )
    return annotated_image

# Function to initialize the camera
def initialize_camera():
    cap = cv2.VideoCapture('/dev/video42') #Camera  # Comment for tfhe laptop
    #cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open the camera.")
        sys.exit()
    return cap

# Function to start recording
def start_recording(cap, filename):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"{filename}_{timestamp}.avi"
    output_directory = "/mnt/sdcard"
    
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    output_file = os.path.join(output_directory, filename)  # Output video file name
    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    out = cv2.VideoWriter(output_file, fourcc, 20.0, (frame_width, frame_height))


    print("Recording started. Press 'q' to stop.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to grab frame.")
            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        detection_result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb))
        annotated_frame = draw_landmarks_on_image(frame_rgb, detection_result)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(annotated_frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

        out.write(cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR))
        #cv2.imshow("Recording", cv2.cvtColor(annotated_frame, cv2.COLOR_RGB2BGR))

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Recording stopped.")
            break

    out.release()
    cv2.destroyAllWindows()

# Main function
def main():
    args = parse_args()
    filename = args.filename

    model_path = os.path.join(current_directory, 'pose_landmarker_full.task')
    if not os.path.exists(model_path):
        print(f"Error: Model file '{model_path}' not found.")
        sys.exit()

    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.PoseLandmarkerOptions(base_options=base_options, output_segmentation_masks=True)
    global detector
    detector = vision.PoseLandmarker.create_from_options(options)

    cap = initialize_camera()

    if args.action == 'start':
        start_recording(cap, filename)
    elif args.action == 'stop':
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)
    else:
        # Original interactive mode
        while True:
            print("Press 'r' to start recording or 'q' to quit.")
            cv2.imshow("Options", np.zeros((100, 400, 3), dtype=np.uint8))
            key = cv2.waitKey(0) & 0xFF
            if key == ord('r'):
                start_recording(cap, filename)
            elif key == ord('q'):
                print("Exiting...")
                cap.release()
                cv2.destroyAllWindows()
                break
            else:
                print("Invalid input. Press 'r' to record or 'q' to quit.")

if __name__ == "__main__":
    main()
