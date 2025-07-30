#!/bin/bash

echo "📟 Monitoring GPIO 17 on gpiochip0 (Press Ctrl+C to exit)"

# Set GPIO 17 as input with pull-up
gpioset gpiochip0 17=tri-hi

while true; do
    val=$(gpioget gpiochip0 17 2>/dev/null)
    if [ "$val" == "0" ]; then
        echo "🔴 Button Pressed"
    else
        echo "⚪ Button Not Pressed"
    fi
    sleep 0.3
done
