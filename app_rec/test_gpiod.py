#!/usr/bin/env python3
"""
Test script for gpiod library
"""

import gpiod
import time

# GPIO pins
BUTTON_PIN = 17
LED_PIN = 27

def test_gpiod():
    """Test gpiod functionality"""
    print("Testing gpiod functionality...")
    
    try:
        # Open GPIO chip
        chip = gpiod.Chip('gpiochip0')
        print("✅ GPIO chip opened successfully")
        
        # Get lines
        button_line = chip.get_line(BUTTON_PIN)
        led_line = chip.get_line(LED_PIN)
        print("✅ GPIO lines obtained")
        
        # Configure button as input with pull-up
        button_line.request(consumer="button", type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
        print("✅ Button configured as input with pull-up")
        
        # Configure LED as output
        led_line.request(consumer="led", type=gpiod.LINE_REQ_DIR_OUT)
        print("✅ LED configured as output")
        
        # Test LED
        print("Testing LED...")
        led_line.set_value(1)
        time.sleep(1)
        led_line.set_value(0)
        print("✅ LED test completed")
        
        # Test button
        print("Testing button (press button to continue)...")
        last_state = 1
        
        for i in range(50):  # Test for 5 seconds
            current_state = button_line.get_value()
            
            if current_state == 0 and last_state == 1:
                print("✅ Button pressed!")
                led_line.set_value(1)
                time.sleep(0.5)
                led_line.set_value(0)
                break
            
            last_state = current_state
            time.sleep(0.1)
        else:
            print("⚠️  No button press detected (this is OK if button not connected)")
        
        print("✅ gpiod test completed successfully!")
        
    except Exception as e:
        print(f"❌ gpiod test failed: {e}")
        return False
    finally:
        try:
            chip.close()
        except:
            pass
    
    return True

if __name__ == "__main__":
    test_gpiod() 