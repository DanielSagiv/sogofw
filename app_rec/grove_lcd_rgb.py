# grove_lcd_rgb.py
import time
from smbus2 import SMBus

DISPLAY_RGB_ADDR = 0x60
DISPLAY_TEXT_ADDR = 0x3e

bus = SMBus(1)

def text_command(cmd):
    bus.write_byte_data(DISPLAY_TEXT_ADDR, 0x80, cmd)

def set_text(text):
    text_command(0x01)  # clear display
    time.sleep(0.05)
    text_command(0x08 | 0x04)
    text_command(0x28)
    time.sleep(0.05)
    count = 0
    row = 0
    for c in text:
        if c == '\n' or count == 16:
            count = 0
            row += 1
            if row == 2:
                break
            text_command(0xc0)
            if c == '\n':
                continue
        count += 1
        bus.write_byte_data(DISPLAY_TEXT_ADDR, 0x40, ord(c))

def set_rgb(r, g, b):
    bus.write_byte_data(DISPLAY_RGB_ADDR, 0, 0)
    bus.write_byte_data(DISPLAY_RGB_ADDR, 1, 0)
    bus.write_byte_data(DISPLAY_RGB_ADDR, 0x08, 0xaa)
    bus.write_byte_data(DISPLAY_RGB_ADDR, 4, r)
    bus.write_byte_data(DISPLAY_RGB_ADDR, 3, g)
    bus.write_byte_data(DISPLAY_RGB_ADDR, 2, b)
