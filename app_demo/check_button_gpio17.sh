#!/bin/bash

CHIP="gpiochip0"
LINE=17

echo "📟 Monitoring GPIO $LINE on $CHIP (Press Ctrl+C to exit)"

while true; do
    val=$(gpioget $CHIP $LINE 2>/dev/null)
    if [ "$val" = "0" ]; then
        echo "🔴 Button Pressed"
    elif [ "$val" = "1" ]; then
        echo "⚪️ Button Not Pressed"
    else
        echo "⚠️ GPIO read error or unknown state: '$val'"
    fi
    sleep 0.3
done
