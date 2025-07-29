#ifndef __CAMERA_IMU_H
#define __CAMERA_IMU_H

#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <stdbool.h>

// IMU data structures
typedef struct {
    float x, y, z;
    double timestamp;
} imu_accel_t;

typedef struct {
    float x, y, z;
    double timestamp;
} imu_gyro_t;

typedef struct {
    float i, j, k, real;
    double timestamp;
    float accuracy;
} imu_rotation_vector_t;

// Function declarations
int camera_imu_start(void);
void camera_imu_stop(void);
int camera_imu_get_data(char *buf, int len);
int camera_imu_get_accel(imu_accel_t *accel);
int camera_imu_get_gyro(imu_gyro_t *gyro);
int camera_imu_get_rotation_vector(imu_rotation_vector_t *rv);

#endif 