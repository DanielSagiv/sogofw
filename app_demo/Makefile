
#CC := gcc #/home/khadas/prebuilts/gcc/linux-x86/aarch64/gcc-arm-10.3-2021.07-x86_64-aarch64-none-linux-gnu/bin/aarch64-rockchip1031-linux-gnu-gcc
#CC := /home/khadas/buildroot/bin/aarch64-buildroot-linux-gnu-gcc

CC := gcc 
#SYSROOT := --sysroot=/home/khadas/buildroot/aarch64-buildroot-linux-gnu/sysroot

CFLAGS := -g -lm #-lpthread -Wall 
CFLAGS += `pkg-config --cflags --libs glib-2.0` -L lib64/ -I imu/ -I gps/ -I camera/ -I input/

OBJS := \
  app/app_main.o \
	gps/gps.o \
	imu/camera_imu.o \
	input/ble_button.o

all: app_demo

app_demo: $(OBJS)
	@$(CC) -o $@ $(OBJS) $(SYSROOT) $(CFLAGS)

%.o: %.c
	@$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS)
