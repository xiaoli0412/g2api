"""Gemini2API launcher - ensures correct working directory for frozen EXE."""
import os
import sys

def main():
    # When running as frozen EXE, set working directory to EXE location
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        os.chdir(exe_dir)
        
        # Copy config template if no config.json exists
        config_path = os.path.join(exe_dir, "config.json")
        template_path = os.path.join(exe_dir, "config.example.json")
        if not os.path.exists(config_path) and os.path.exists(template_path):
            import shutil
            shutil.copy2(template_path, config_path)
    
    # Ensure the package is importable
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
    
    # Launch the main GUI
    from app import main as app_main
    app_main()

if __name__ == "__main__":
    main()
