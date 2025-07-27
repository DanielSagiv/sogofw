#include <stdio.h>
#include <linux/types.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <fcntl.h>
#include <unistd.h>
#include <math.h>
#include <sys/types.h>
#include <sys/ioctl.h>
#include <errno.h>
#include <assert.h>
#include <string.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>

#include "bno055_api.h"

//extern UART_HandleTypeDef huart1;
//extern I2C_HandleTypeDef hi2c1;
struct bno055_t myBNO;
static int i2c_fd = -1;

static s8 bno055_write(u8 dev_addr, u8 reg_addr, u8 *data, u8 len)
{
  //int ret;
  //ret = i2c_write_bytes(g_fd, dev_addr, reg_addr, reg_data, wr_len);
  //return ret;

  uint8_t *outbuf = NULL;
  struct i2c_rdwr_ioctl_data packets;
  struct i2c_msg messages[1];

  if (i2c_fd < 0)
  {
      printf("Error: No i2c file to write\n");
      return -1;
  }

  outbuf = malloc(len + 1);
  if (!outbuf)
  {
      printf("Error: No memory for buffer\n");
      return -1;
  }

  outbuf[0] = reg_addr;
  memcpy(outbuf + 1, data, len);

  messages[0].addr = dev_addr;
  messages[0].flags = 0;
  messages[0].len = len + 1;
  messages[0].buf = outbuf;

  /* Transfer the i2c packets to the kernel and verify it worked */
  packets.msgs = messages;
  packets.nmsgs = 1;
  if (ioctl(i2c_fd, I2C_RDWR, &packets) < 0)
  {
      printf("Error: Unable to send data");
      free(outbuf);
      return -1;
  }

  free(outbuf);

  return 0;
}

static s8 bno055_read(u8 dev_addr, u8 reg_addr, u8 *data, u8 len)
{
  //int ret;
  //ret = i2c_read_bytes(g_fd, dev_addr, reg_addr, reg_data, r_len);
  //return ret;

  uint8_t outbuf[1];
  struct i2c_rdwr_ioctl_data packets;
  struct i2c_msg messages[2];

  if (i2c_fd < 0)
  {
      printf("Error: No i2c file to read\n");
      return -1;
  }

  outbuf[0] = reg_addr;
  messages[0].addr = dev_addr;
  messages[0].flags = 0;
  messages[0].len = sizeof(outbuf);
  messages[0].buf = outbuf;

  /* The data will get returned in this structure */
  messages[1].addr = dev_addr;
  messages[1].flags = I2C_M_RD/* | I2C_M_NOSTART*/;
  messages[1].len = len;
  messages[1].buf = data;

  /* Send the request to the kernel and get the result back */
  packets.msgs = messages;
  packets.nmsgs = 2;
  if (ioctl(i2c_fd, I2C_RDWR, &packets) < 0)
  {
      printf("Error: Unable to send data");
      return -1;
  }

  return 0;
}

void bno055_delay(u32 ms)
{
  usleep(ms * 1000);
}

s8 bno055_read_gyro(struct bno055_gyro_t *gyro)
{
  BNO055_RETURN_FUNCTION_TYPE ret;

  ret = bno055_read_gyro_xyz(gyro);
  if (ret == BNO055_SUCCESS)
  {
  	//printf("GYRO:x=%d, y=%d, z=%d\r\n", gyro->x, gyro->y, gyro->z);
  	return 0;
  }
  return 1;
}

s8 bno055_read_acc(struct bno055_accel_t *acc)
{
  BNO055_RETURN_FUNCTION_TYPE ret;
  ret = bno055_read_accel_xyz(acc);
  if (ret == BNO055_SUCCESS)
  {
  	//printf("ACC:x=%d, y=%d, z=%d\r\n",acc->x, acc->y, acc->z);
  	return 0;
  }
  return 1;
}

s8 bno055_read_mag(struct bno055_mag_t *mag)
{
  BNO055_RETURN_FUNCTION_TYPE ret;

  ret = bno055_read_mag_xyz(mag);
  if (ret == BNO055_SUCCESS)
  {
    //printf("MAG:x=%d, y=%d, z=%d\r\n",mag->x, mag->y, mag->z);
    return 0;
  }
  return 1;
}

void bno055_start(void)
{
    //	char *err = "bno055 init failed...\r\n";
    //	char *sta = "bno055 init succeed!!!\r\n";
  u8 gyro_calib_stat;
  BNO055_RETURN_FUNCTION_TYPE ret;
  u8 wait_cnt = 20;

  myBNO.bus_read = bno055_read;
  myBNO.bus_write = bno055_write;
  myBNO.delay_msec = bno055_delay;
  myBNO.dev_addr = BNO055_I2C_ADDR1;

  i2c_fd = open("/dev/i2c-6", O_RDWR);
  if (i2c_fd < 0)
  {
    printf("can not open file %s\n", "/dev/i2c-6");
    return;
  }

  ret = bno055_init(&myBNO);
  printf("bno init:%d\n", ret);

  bno055_set_sys_rst(BNO055_BIT_ENABLE);
  bno055_delay(1000);

  ret = bno055_set_operation_mode(BNO055_OPERATION_MODE_NDOF);

  while(wait_cnt--)
  {
  	ret += bno055_get_gyro_calib_stat(&gyro_calib_stat);
  	if (ret == BNO055_SUCCESS && gyro_calib_stat==3)
  	{
      printf("bno055 init succeed!\r\n");
      break;
  	}
  	bno055_delay(1000);
  	printf("bno055 init failed and retry!\r\n");
  }
}

void bno055_stop(void)
{
  i2c_fd = open("/dev/i2c-6", O_RDWR);
  if (i2c_fd >= 0)
  {
    close(i2c_fd);
    i2c_fd = -1;
  }
}

int bno055_data(char *buf, int len)
{
  struct bno055_gyro_t gyro;
  struct bno055_accel_t acc;
  struct bno055_mag_t mag;
  float euler_h;
  float euler_r;
  float euler_p;
  int ind;

  printf("\r\n");
  bno055_read_gyro(&gyro);
  bno055_read_acc(&acc);
  bno055_read_mag(&mag);

  memset(buf, 0, len);
  sprintf(buf, "GYRO:x=%d, y=%d, z=%d\r\n", gyro.x, gyro.y, gyro.z);
  ind = strlen(buf);
  sprintf(buf +ind, "ACC:x=%d, y=%d, z=%d\r\n",acc.x, acc.y, acc.z);
  ind = strlen(buf);
  sprintf(buf + ind, "MAG:x=%d, y=%d, z=%d\r\n",mag.x, mag.y, mag.z);
  ind = strlen(buf);

#if 0
  bno055_convert_float_euler_h_deg(&euler_h);
  bno055_convert_float_euler_r_deg(&euler_r);
  bno055_convert_float_euler_h_deg(&euler_p);
  sprintf(buf + ind, "Head=%f, Roll=%f, Pitch=%f\r\n", euler_h, euler_r, euler_p);
  ind = strlen(buf);
#endif

  return ind;
}

int bno055_get_accxy(float *ac)
{
  struct bno055_accel_t acc;
  float xy;
  int ret;

  ret = bno055_read_acc(&acc);
  xy = pow(acc.x, 2) + pow(acc.y, 2);
  xy = pow(xy, 0.5);
  if (ac)
  {
    *ac = xy;
  }

  //printf("ACC:x=%d, y=%d, z=%d, xy=%f\r\n", acc.x, acc.y, acc.z, *ac);

  return ret;
}

int main_test(void)
{
  struct bno055_gyro_t gyro;
  struct bno055_accel_t acc;
  struct bno055_mag_t mag;
  float euler_h;
  float euler_r;
  float euler_p;
  float xy;

  bno055_start();

  for (int i = 0; i < 100; i++)
  {
    printf("\r\n");
    bno055_read_gyro(&gyro);
    bno055_read_acc(&acc);
    bno055_get_accxy(&xy);
    bno055_read_mag(&mag);

#if 0
    printf("GYRO:x=%d, y=%d, z=%d\r\n", gyro.x, gyro.y, gyro.z);
    printf("ACC:x=%d, y=%d, z=%d\r\n",acc.x, acc.y, acc.z);
    printf("MAG:x=%d, y=%d, z=%d\r\n",mag.x, mag.y, mag.z);

    //printf("\r\n");
    bno055_convert_float_euler_h_deg(&euler_h);
    bno055_convert_float_euler_r_deg(&euler_r);
    bno055_convert_float_euler_h_deg(&euler_p);
    printf("Head=%f, Roll=%f, Pitch=%f\n", euler_h, euler_r, euler_p);
#endif

    sleep(1);
  }

  return 0;
}

