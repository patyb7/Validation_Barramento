# delete_pycache.py
import os
import shutil

for root, dirs, files in os.walk(os.getcwd()):
    if '__pycache__' in dirs:
        shutil.rmtree(os.path.join(root, '__pycache__'))
        print(f"Removed: {os.path.join(root, '__pycache__')}")