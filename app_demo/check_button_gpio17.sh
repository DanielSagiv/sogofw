#!/bin/bash
echo "Monitoring GPIO 17 using libgpiod (Press Ctrl+C to exit)"
while true; do
    val=$(gpioget gpiochip4 17)
    if [ "$val" -eq 0 ]; then
        echo "🔴 Button Pressed"
    else
        echo "⚪️ Button Not Pressed"
    fi
    sleep 0.3
done
