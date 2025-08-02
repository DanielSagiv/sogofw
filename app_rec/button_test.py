from gpiozero import Button
from signal import pause

button = Button(17)  # GPIO17

def on_press():
    print("Button Pressed")

button.when_pressed = on_press

print("Waiting for button press...")
pause()
