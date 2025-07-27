#ifndef __GPS_H
#define __GPS_H

#include "stdio.h"
#include <unistd.h>
#include "string.h"

int gps_open(void);
int gps_close(int fd);
int gps_outdata(int fd, char *data, int len);
#endif
