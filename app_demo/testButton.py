from gpiozero import Button
from signal import pause

button = Button(17)  # GPIO17 = physical pin 11

def pressed():
    print("Button Pressed!")

button.when_pressed = pressed

pause()
#sdvsdfvdsf
