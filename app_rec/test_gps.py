#!/usr/bin/env python3
"""
Test script for GPS functionality
"""

import serial
import time
import json
from pathlib import Path

def test_gps_connection():
    """Test GPS serial connection and data parsing"""
    print("Testing GPS connection...")
    
    try:
        # Open serial connection to GPS
        gps_serial = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)
        print("✅ GPS serial connection opened successfully")
        
        # Test reading GPS data
        print("Reading GPS data for 10 seconds...")
        start_time = time.time()
        
        while time.time() - start_time < 10:
            try:
                gps_line = gps_serial.readline().decode('utf-8', errors='ignore').strip()
                
                if gps_line and gps_line.startswith('$'):
                    print(f"GPS: {gps_line}")
                    
                    # Test parsing
                    if gps_line.startswith('$GPGGA') or gps_line.startswith('$GPRMC'):
                        parts = gps_line.split(',')
                        if len(parts) >= 5:
                            lat = parts[2] if parts[2] else "N/A"
                            lon = parts[4] if parts[4] else "N/A"
                            print(f"   Location: {lat}, {lon}")
                
            except Exception as e:
                print(f"Error reading GPS: {e}")
                break
        
        gps_serial.close()
        print("✅ GPS test completed successfully")
        
    except Exception as e:
        print(f"❌ GPS test failed: {e}")

if __name__ == "__main__":
    test_gps_connection() 