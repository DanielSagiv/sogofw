#include "camera_imu.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/time.h>

// Global variables for IMU data
static pthread_mutex_t imu_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool imu_running = false;
static pthread_t imu_thread;

// Latest IMU data
static imu_accel_t latest_accel = {0};
static imu_gyro_t latest_gyro = {0};
static imu_rotation_vector_t latest_rv = {0};
static bool has_accel_data = false;
static bool has_gyro_data = false;
static bool has_rv_data = false;

// Python script for IMU data collection
static const char* imu_script = 
"#!/usr/bin/env python3\n"
"import cv2\n"
"import depthai as dai\n"
"import time\n"
"import math\n"
"import sys\n"
"import json\n"
"\n"
"# Create pipeline\n"
"pipeline = dai.Pipeline()\n"
"\n"
"# Define sources and outputs\n"
"imu = pipeline.create(dai.node.IMU)\n"
"xlinkOut = pipeline.create(dai.node.XLinkOut)\n"
"\n"
"xlinkOut.setStreamName(\"imu\")\n"
"\n"
"# Enable IMU sensors\n"
"imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 500)\n"
"imu.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)\n"
"imu.enableIMUSensor(dai.IMUSensor.ROTATION_VECTOR, 400)\n"
"\n"
"imu.setBatchReportThreshold(1)\n"
"imu.setMaxBatchReports(10)\n"
"\n"
"# Link plugins IMU -> XLINK\n"
"imu.out.link(xlinkOut.input)\n"
"\n"
"# Pipeline is defined, now we can connect to the device\n"
"with dai.Device(pipeline) as device:\n"
"    def timeDeltaToMilliS(delta) -> float:\n"
"        return delta.total_seconds()*1000\n"
"\n"
"    # Output queue for imu bulk packets\n"
"    imuQueue = device.getOutputQueue(name=\"imu\", maxSize=50, blocking=False)\n"
"    baseTs = None\n"
"    \n"
"    while True:\n"
"        try:\n"
"            imuData = imuQueue.get()  # blocking call\n"
"\n"
"            imuPackets = imuData.packets\n"
"            for imuPacket in imuPackets:\n"
"                data = {}\n"
"                \n"
"                # Get accelerometer data\n"
"                if hasattr(imuPacket, 'acceleroMeter'):\n"
"                    acceleroValues = imuPacket.acceleroMeter\n"
"                    acceleroTs = acceleroValues.getTimestampDevice()\n"
"                    if baseTs is None:\n"
"                        baseTs = acceleroTs\n"
"                    acceleroTs = timeDeltaToMilliS(acceleroTs - baseTs)\n"
"                    \n"
"                    data['accel'] = {\n"
"                        'x': acceleroValues.x,\n"
"                        'y': acceleroValues.y,\n"
"                        'z': acceleroValues.z,\n"
"                        'timestamp': acceleroTs\n"
"                    }\n"
"                \n"
"                # Get gyroscope data\n"
"                if hasattr(imuPacket, 'gyroscope'):\n"
"                    gyroValues = imuPacket.gyroscope\n"
"                    gyroTs = gyroValues.getTimestampDevice()\n"
"                    if baseTs is None:\n"
"                        baseTs = gyroTs\n"
"                    gyroTs = timeDeltaToMilliS(gyroTs - baseTs)\n"
"                    \n"
"                    data['gyro'] = {\n"
"                        'x': gyroValues.x,\n"
"                        'y': gyroValues.y,\n"
"                        'z': gyroValues.z,\n"
"                        'timestamp': gyroTs\n"
"                    }\n"
"                \n"
"                # Get rotation vector data\n"
"                if hasattr(imuPacket, 'rotationVector'):\n"
"                    rVvalues = imuPacket.rotationVector\n"
"                    rvTs = rVvalues.getTimestampDevice()\n"
"                    if baseTs is None:\n"
"                        baseTs = rvTs\n"
"                    rvTs = timeDeltaToMilliS(rvTs - baseTs)\n"
"                    \n"
"                    data['rotation_vector'] = {\n"
"                        'i': rVvalues.i,\n"
"                        'j': rVvalues.j,\n"
"                        'k': rVvalues.k,\n"
"                        'real': rVvalues.real,\n"
"                        'accuracy': rVvalues.rotationVectorAccuracy,\n"
"                        'timestamp': rvTs\n"
"                    }\n"
"                \n"
"                # Output JSON data\n"
"                if data:\n"
"                    print(json.dumps(data))\n"
"                    sys.stdout.flush()\n"
"        except KeyboardInterrupt:\n"
"            break\n"
"        except Exception as e:\n"
"            print(f\"Error: {e}\", file=sys.stderr)\n"
"            break\n";

// Function to parse JSON IMU data
static int parse_imu_json(const char* json_str, imu_accel_t* accel, imu_gyro_t* gyro, imu_rotation_vector_t* rv) {
    // Simple JSON parsing for our specific format
    // In a real implementation, you'd use a proper JSON library
    
    if (strstr(json_str, "\"accel\"")) {
        // Parse accelerometer data
        // This is a simplified parser - in production use a proper JSON library
        sscanf(json_str, "{\"accel\":{\"x\":%f,\"y\":%f,\"z\":%f,\"timestamp\":%lf}", 
               &accel->x, &accel->y, &accel->z, &accel->timestamp);
        return 1;
    }
    
    if (strstr(json_str, "\"gyro\"")) {
        // Parse gyroscope data
        sscanf(json_str, "{\"gyro\":{\"x\":%f,\"y\":%f,\"z\":%f,\"timestamp\":%lf}", 
               &gyro->x, &gyro->y, &gyro->z, &gyro->timestamp);
        return 2;
    }
    
    if (strstr(json_str, "\"rotation_vector\"")) {
        // Parse rotation vector data
        sscanf(json_str, "{\"rotation_vector\":{\"i\":%f,\"j\":%f,\"k\":%f,\"real\":%f,\"accuracy\":%f,\"timestamp\":%lf}", 
               &rv->i, &rv->j, &rv->k, &rv->real, &rv->accuracy, &rv->timestamp);
        return 3;
    }
    
    return 0;
}

// IMU data collection thread
static void* imu_data_thread(void* arg) {
    FILE* script_file = NULL;
    FILE* imu_pipe = NULL;
    char line[512];
    
    // Create temporary Python script
    script_file = fopen("/tmp/camera_imu_script.py", "w");
    if (!script_file) {
        printf("Error: Cannot create IMU script file\n");
        return NULL;
    }
    
    fprintf(script_file, "%s", imu_script);
    fclose(script_file);
    
    // Make script executable
    system("chmod +x /tmp/camera_imu_script.py");
    
    // Start IMU data collection
    imu_pipe = popen("/tmp/camera_imu_script.py", "r");
    if (!imu_pipe) {
        printf("Error: Cannot start IMU data collection\n");
        return NULL;
    }
    
    printf("IMU data collection started\n");
    
    while (imu_running) {
        if (fgets(line, sizeof(line), imu_pipe)) {
            // Remove newline
            line[strcspn(line, "\n")] = 0;
            
            imu_accel_t accel = {0};
            imu_gyro_t gyro = {0};
            imu_rotation_vector_t rv = {0};
            
            int result = parse_imu_json(line, &accel, &gyro, &rv);
            
            pthread_mutex_lock(&imu_mutex);
            
            if (result == 1) {
                latest_accel = accel;
                has_accel_data = true;
            } else if (result == 2) {
                latest_gyro = gyro;
                has_gyro_data = true;
            } else if (result == 3) {
                latest_rv = rv;
                has_rv_data = true;
            }
            
            pthread_mutex_unlock(&imu_mutex);
        }
    }
    
    // Cleanup
    pclose(imu_pipe);
    unlink("/tmp/camera_imu_script.py");
    
    return NULL;
}

int camera_imu_start(void) {
    if (imu_running) {
        printf("IMU already running\n");
        return 0;
    }
    
    imu_running = true;
    
    if (pthread_create(&imu_thread, NULL, imu_data_thread, NULL)) {
        printf("Error: Cannot create IMU thread\n");
        imu_running = false;
        return -1;
    }
    
    // Wait a bit for initialization
    usleep(1000000); // 1 second
    
    printf("Camera IMU started successfully\n");
    return 0;
}

void camera_imu_stop(void) {
    if (!imu_running) {
        return;
    }
    
    imu_running = false;
    
    // Wait for thread to finish
    pthread_join(imu_thread, NULL);
    
    printf("Camera IMU stopped\n");
}

int camera_imu_get_data(char *buf, int len) {
    pthread_mutex_lock(&imu_mutex);
    
    // Format data similar to the original BNO055 format
    int written = 0;
    
    if (has_accel_data && has_gyro_data) {
        written = snprintf(buf, len, "%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n",
                          latest_accel.x, latest_accel.y, latest_accel.z,
                          latest_gyro.x, latest_gyro.y, latest_gyro.z,
                          latest_rv.i, latest_rv.j, latest_rv.k);
    } else if (has_accel_data) {
        written = snprintf(buf, len, "%.6f,%.6f,%.6f,0.0,0.0,0.0,0.0,0.0,0.0\n",
                          latest_accel.x, latest_accel.y, latest_accel.z);
    } else if (has_gyro_data) {
        written = snprintf(buf, len, "0.0,0.0,0.0,%.6f,%.6f,%.6f,0.0,0.0,0.0\n",
                          latest_gyro.x, latest_gyro.y, latest_gyro.z);
    }
    
    pthread_mutex_unlock(&imu_mutex);
    
    return written;
}

int camera_imu_get_accel(imu_accel_t *accel) {
    pthread_mutex_lock(&imu_mutex);
    
    if (has_accel_data) {
        *accel = latest_accel;
        pthread_mutex_unlock(&imu_mutex);
        return 0;
    }
    
    pthread_mutex_unlock(&imu_mutex);
    return -1;
}

int camera_imu_get_gyro(imu_gyro_t *gyro) {
    pthread_mutex_lock(&imu_mutex);
    
    if (has_gyro_data) {
        *gyro = latest_gyro;
        pthread_mutex_unlock(&imu_mutex);
        return 0;
    }
    
    pthread_mutex_unlock(&imu_mutex);
    return -1;
}

int camera_imu_get_rotation_vector(imu_rotation_vector_t *rv) {
    pthread_mutex_lock(&imu_mutex);
    
    if (has_rv_data) {
        *rv = latest_rv;
        pthread_mutex_unlock(&imu_mutex);
        return 0;
    }
    
    pthread_mutex_unlock(&imu_mutex);
    return -1;
} 