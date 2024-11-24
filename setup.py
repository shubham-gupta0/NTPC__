#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
import os 

def setup_environment():
    """Setup virtual environment and install dependencies"""
    try:
        # Specify virtual environment name
        venv_name = "myenv"
        venv_path = Path(os.getcwd()) / venv_name


        # Commands to be executed
        commands = [
            f"py -3.9 -m venv {venv_path}",  # Create virtual environment
            
            # Activate venv and install dependencies (Windows vs Unix)
            f"{'call' if sys.platform == 'win32' else 'source'} "
            f"{venv_path}/{'Scripts' if sys.platform == 'win32' else 'bin'}/activate "
            "&& python -m pip install --upgrade pip "
            "&& pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu117"
            "&& pip3 install -r requirements.txt "
            "&& python download_models/download_doctr_model.py "
            "&& python download_models/download_qwen_model.py "
        ]

        # Execute commands
        for cmd in commands:
            print(f"Executing: {cmd}")
            subprocess.run(cmd, shell=True, check=True)
            
        print("\nSetup completed successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"Error during setup: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_environment()