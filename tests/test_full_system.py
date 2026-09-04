import sys
import os
import time
import subprocess

py_bin = sys.executable

print("Starting all 5 processes (P3, P4, P1, P2, P0)...")
p3 = subprocess.Popen([py_bin, "src/p3.py"])
p4 = subprocess.Popen([py_bin, "src/p4.py"])
time.sleep(0.5)

p1 = subprocess.Popen([py_bin, "src/p1.py"])
p2 = subprocess.Popen([py_bin, "src/p2.py"])
time.sleep(0.5)

p0 = subprocess.Popen([py_bin, "src/p0.py", "--auto"])

try:
    p0.wait(timeout=15)
finally:
    p0.terminate()
    p1.terminate()
    p2.terminate()
    p3.terminate()
    p4.terminate()
