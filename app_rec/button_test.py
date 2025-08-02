import RPi.GPIO as GPIO
import time

BUTTON_GPIO = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("Press the button...")

try:
    while True:
        if GPIO.input(BUTTON_GPIO) == GPIO.LOW:
            print("Button Pressed")
        time.sleep(0.1)

except KeyboardInterrupt:
    GPIO.cleanup()
    print("Clean exit.")
