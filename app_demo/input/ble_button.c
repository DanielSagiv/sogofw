/**
 * @file input_test.c
 *
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <signal.h>
#include <linux/input.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int find_event(char *event)
{
  int fd;
  FILE *fp;
  struct stat tStat;
  char  *file_buff;
  char *buff;

  /*Handlers=kbd mouse1 event7 */
  char sub_buff1[] = "Handlers=kbd mouse";
  /* Handlers=sysrq kbd leds mouse0 event6 */
  char sub_buff2[] = "Handlers=sysrq kbd leds mouse";
  char file_path[] = "./log.txt";
  //char *argv[]={"bash", "cat", "/proc/bus/input/devices", ">", "./log.txt", NULL};

  /* According  to kbd name find event number*/

  signal(SIGCHLD, SIG_IGN);
  system("cat /proc/bus/input/devices > ./log.txt");
  signal(SIGCHLD, SIG_DFL);
  //execl("/bin/cat", "cat", "/proc/bus/input/devices",  ">", "log.txt", NULL);

  fp = fopen(file_path, "r+");
  if (fp == NULL)
  {
    printf("Can't open %s\n", file_path);
    return -1;
  }

  fd = fileno(fp);
  fstat(fd, &tStat);

  /* mmap the file to mem */
  file_buff = (unsigned char *)mmap(NULL , tStat.st_size,
          PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
  if (file_buff == (char *) -1)
  {
    printf("mmap error!\n");
    fclose(fp);
    remove("./log.txt");
    return -1;
  }

  /* In the mem file_buff  find sub_buff name */
  buff = strstr(file_buff, sub_buff1);
  if (NULL == buff)
  {
    buff = strstr(file_buff, sub_buff2);
    if (NULL == buff)
    {
    	printf("can't find %s\n", sub_buff2);
    	munmap(file_buff, tStat.st_size);
        fclose(fp);
        remove("./log.txt");
        return -1;
    }
    else
    {
      memcpy(event, buff + strlen(sub_buff2) + 7, 2);
    }
  }
  else
  {
    memcpy(event, buff + strlen(sub_buff1) + 7, 2);
  }

  munmap(file_buff, tStat.st_size);
  fclose(fp);
  remove("./log.txt");

  return  0;
}

int get_ble_button(void)
{
  char filename[] = "/dev/input/event99";
  int ret = 0;
  int f = 0;
  int code;

  struct input_event inputevent;

  ret = find_event(filename + 16);
  if (ret < 0)
  {
    printf("no ble button\r\n");
    return -1;
  }

  if (filename[17] < '0' || filename[17] > '9')
  {
    filename[17] = 0;
  }

  //printf("open file %s\r\n", filename);
  f = open(filename, O_RDWR);
  if (f < 0)
  {
    printf("file open error\r\n");
    return -1;
  }

  while(1)
  {
    code = -1;
    ret = read(f, &inputevent, sizeof(inputevent));
    if (ret < 0)
    {
      printf("data read error\r\n");
      break;
    }
    else
    {
      //printf("type %d\r\n", inputevent.type);
      switch(inputevent.type)
      {
        case EV_SYN:
          break;
        case EV_KEY:
          code = inputevent.value ? inputevent.code : 0;
          printf("key %x %x\r\n", code, inputevent.value);
          break;
        case EV_REL:
          break;
      }

      if (code > 0)
      {
        break;
      }
    }
  }

  close(f);
  return code;
}

int maint(int argc,char *argv[])
{
  char buff[3];
  int ret;

  memset(buff, 0, sizeof(buff));
  ret = find_event(buff);
  printf("event%s\n", buff);

  if (ret < 0)
  {
    return 0;
  }

  while(1)
  {
    get_ble_button();
    sleep(1);
  }
  return 0;
}
