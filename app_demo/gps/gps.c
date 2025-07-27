#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>

// set serial path
#define SERIAL_PORT "/dev/ttyS7"

int gps_open(void)
{
  struct termios tty;
  int fd = -1;

  // open
  fd = open(SERIAL_PORT, O_RDWR | O_NOCTTY, 0777);
  if (fd < 0)
  {
    perror("Error opening serial port");
    return -1;
  }

  // Configuration of serial
  memset(&tty, 0, sizeof(tty));
  if (tcgetattr(fd, &tty) != 0)
  {
    perror("Error getting serial port attributes");
    close(fd);
    return -1;
  }

  cfsetospeed(&tty, B9600); // set baud rate
  cfsetispeed(&tty, B9600);

  tty.c_cflag |= (CLOCAL | CREAD);
  tty.c_cflag &= ~PARENB;
  tty.c_cflag &= ~CSTOPB;
  tty.c_cflag &= ~CSIZE;
  tty.c_cflag |= CS8;

  tty.c_lflag &= ~(ECHO | ICANON);

  // write configration to serial
  if (tcsetattr(fd, TCSANOW, &tty) != 0)
  {
      perror("Error setting serial port attributes");
      close(fd);
      return -1;
  }

  printf("Start gps test\n");

  return fd;
}

int gps_close(int fd)
{
  close(fd);
}

int gps_outdata(int fd, char *data, int len)
{
  int ret;

  memset(data, 0, len);
  ret = read(fd, data, len);
  if (ret > 0)
  {
    //printf("%s", data);
  }

  return ret;
}

int main_gps(void)
{
  int fd;
  int cnt = 300;
  char gps_data[256];

  fd = gps_open();

  while (cnt-- > 0)
  {
    gps_outdata(fd, gps_data, sizeof(gps_data));
  }

  gps_close(fd);
}
