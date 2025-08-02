#!/usr/bin/env python3
"""
Test script for button-controlled recording
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from rec_vid_btn import MultiCameraRecorder

def test_button_functionality():
    """Test button functionality"""
    print("Testing button-controlled recording system...")
    
    try:
        recorder = MultiCameraRecorder()
        
        print("✅ System initialized successfully")
        print("✅ Button on GPIO17 should be working")
        print("✅ LCD should show 'SOGO READY'")
        print("✅ Press button to start/stop recording")
        print("✅ Press Ctrl+C to exit")
        
        # Start the main loop
        recorder.run()
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")

if __name__ == "__main__":
    test_button_functionality() 