#!/usr/bin/env python3
"""
Test script for skeleton recognition functionality
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from main_no_gpio import MultiCameraRecorder

def test_skeleton_initialization():
    """Test skeleton recognition initialization"""
    print("Testing skeleton recognition initialization...")
    
    try:
        recorder = MultiCameraRecorder()
        
        if recorder.skeleton_enabled:
            print("✅ Skeleton recognition initialized successfully")
            print(f"   - Model loaded: {recorder.pose_detector is not None}")
            print(f"   - Skeleton enabled: {recorder.skeleton_enabled}")
        else:
            print("❌ Skeleton recognition failed to initialize")
            
    except Exception as e:
        print(f"❌ Error during initialization: {e}")

def test_model_files():
    """Test if skeleton model files exist"""
    print("\nTesting skeleton model files...")
    
    models_dir = Path(__file__).parent / "models"
    model_files = [
        "pose_landmarker_lite.task",
        "pose_landmarker_full.task", 
        "pose_landmarker_heavy.task"
    ]
    
    for model_file in model_files:
        model_path = models_dir / model_file
        if model_path.exists():
            size_mb = model_path.stat().st_size / (1024 * 1024)
            print(f"✅ {model_file}: {size_mb:.1f} MB")
        else:
            print(f"❌ {model_file}: Not found")

if __name__ == "__main__":
    print("🧪 Skeleton Recognition Test")
    print("=" * 40)
    
    test_model_files()
    test_skeleton_initialization()
    
    print("\n✅ Test completed!") 