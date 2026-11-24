"""One-time setup: create directories, initialize database."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from pathlib import Path

DIRS = [
    'data/raw', 'data/processed', 'data/tiles', 'data/predictions',
    'data/vectors', 'data/parcels', 'data/gnss', 'data/exports',
    'models/checkpoints/building', 'models/checkpoints/road',
    'models/checkpoints/landuse', 'models/checkpoints/boundary',
    'models/checkpoints/object_detection', 'models/checkpoints/parcel',
    'models/checkpoints/change_detection', 'models/checkpoints/confidence',
    'models/configs',
]

def main():
    print("Creating directories...")
    for d in DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"  {d}")
    
    print("\nDirectories created. Database will initialize on first backend start.")
    print("Next: add trained model checkpoints to models/checkpoints/")

if __name__ == '__main__':
    main()
