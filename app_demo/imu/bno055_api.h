#ifndef __BNO055_API_H
#define __BNO055_API_H
#include "bno055.h"
#include "stdio.h"
#include <unistd.h>
#include "string.h"

void bno055_start(void);
void bno055_stop(void);
int bno055_data(char *buf, int len);
int bno055_get_accxy(float *ac);
s8 bno055_read_gyro(struct bno055_gyro_t *gyro);
s8 bno055_read_mag(struct bno055_mag_t * mag);
s8 bno055_read_acc(struct bno055_accel_t *acc);
#endif


