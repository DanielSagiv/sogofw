#!/usr/bin/env python3
"""
Simple GPIO test script
"""

import RPi.GPIO as GPIO
import time

# GPIO pins
BUTTON_PIN = 17
LED_PIN = 27

def test_gpio():
    """Test GPIO functionality"""
    print("Testing GPIO functionality...")
    
    try:
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(LED_PIN, GPIO.OUT)
        
        print("✅ GPIO setup successful")
        
        # Test LED
        print("Testing LED...")
        GPIO.output(LED_PIN, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(LED_PIN, GPIO.LOW)
        print("✅ LED test completed")
        
        # Test button
        print("Testing button (press button to continue)...")
        last_state = GPIO.HIGH
        
        for i in range(50):  # Test for 5 seconds
            current_state = GPIO.input(BUTTON_PIN)
            
            if current_state == GPIO.LOW and last_state == GPIO.HIGH:
                print("✅ Button pressed!")
                GPIO.output(LED_PIN, GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(LED_PIN, GPIO.LOW)
                break
            
            last_state = current_state
            time.sleep(0.1)
        else:
            print("⚠️  No button press detected (this is OK if button not connected)")
        
        print("✅ GPIO test completed successfully!")
        
    except Exception as e:
        print(f"❌ GPIO test failed: {e}")
        return False
    finally:
        GPIO.cleanup()
    
    return True

if __name__ == "__main__":
    test_gpio() 