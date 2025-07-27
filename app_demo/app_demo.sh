#!/bin/sh -e

#export LD_LIBRARY_PATH=/usr/lib/gstreamer-1.0
#export XDG_RUNTIME_DIR=/tmp/.xdg

echo "PID of this script: $$"
echo "PPID of this script: $PPID"
echo "UID of this script: $UID"

echo none | sudo tee /sys/class/leds/red_led/trigger
echo none | sudo tee /sys/class/leds/green_led/trigger
echo none | sudo tee /sys/class/leds/blue_led/trigger

while [ -x /home/khadas/prog/app_demo/app_demo ]
do
  /home/khadas/prog/app_demo/app_demo
  
  # Copy video to SD
  #if [ -d /mnt/sd1/mp4 ] && [ -f /home/khadas/video_*.mp4 ]; then
   # sudo cp -f /home/khadas/video_*.mp4 /mnt/sd1/mp4
    #sudo cp -f /home/khadas/gps_*.csv /mnt/sd1/mp4
	#	sudo cp -f /home/khadas/imu_*.csv /mnt/sd1/mp4
		
	  #sudo rm -f /home/khadas/video_*.mp4
	  #sudo rm -f /home/khadas/gps_*.csv
	  #sudo rm -f /home/khadas/imu_*.csv
  #fi'
done
  





