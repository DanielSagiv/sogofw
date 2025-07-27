#!/bin/sh -e

if [ ! -d /sys/class/gpio/gpio114 ]; then
  echo 114 | sudo tee /sys/class/gpio/export
fi
	
echo out | sudo tee /sys/class/gpio/gpio114/direction # Set GPIO output

echo 1 | sudo tee /sys/class/gpio/gpio114/value # Set GPIO output high
sleep 1
echo 0 | sudo tee /sys/class/gpio/gpio114/value # Set GPIO output low

#echo in | sudo tee /sys/class/gpio/gpio114/direction # Set GPIO output
  





