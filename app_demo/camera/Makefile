
##CC := /home/xy/rk3326_release_baidu/buildroot/output/rockchip_rk3326_64/host/bin/aarch64-buildroot-linux-gnu-gcc
##SYSROOT := --sysroot=/home/xy/rk3326_release_baidu/buildroot/output/rockchip_rk3326_64/host/aarch64-buildroot-linux-gnu/sysroot
##CC := gcc #/home/khadas/prebuilts/gcc/linux-x86/aarch64/gcc-arm-10.3-2021.07-x86_64-aarch64-none-linux-gnu/bin/aarch64-rockchip1031-linux-gnu-gcc
##CC := /home/khadas/buildroot/bin/aarch64-buildroot-linux-gnu-gcc

CC := gcc 
#SYSROOT := --sysroot=/home/khadas/buildroot/aarch64-buildroot-linux-gnu/sysroot

all: gstest

OBJS := gstest.o

#ARCH=arm64
CFLAGS := -g #-Wall -g
CFLAGS += `pkg-config --cflags --libs gstreamer-1.0`

gstest: $(OBJS)
	@$(CC) -o gstest $(OBJS) $(SYSROOT) $(CFLAGS)

%.o: %.c
	@$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS)
