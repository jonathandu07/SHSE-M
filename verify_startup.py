# verify_startup.py
import os
import sys
import threading
import time

# CONFIGURATION DU PATH
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Mock Window to avoid "No display" error if possible, 
# although Kivy might still fail.
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONSOLELOG'] = '1'

try:
    from frontend.main import SHSEMApp
    from kivy.clock import Clock
    
    app = SHSEMApp()
    
    def stop_app(dt):
        print("Startup successful, stopping app...")
        app.stop()
        sys.exit(0)

    # Schedule stop after 2 seconds
    Clock.schedule_once(stop_app, 2)
    
    print("Starting Kivy app for verification...")
    app.run()
    
except Exception as e:
    print(f"Startup FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
